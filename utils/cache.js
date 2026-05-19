import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const CACHE_DIR = path.join(__dirname, '..', '.cache');
const CACHE_EXPIRY_MS = 24 * 60 * 60 * 1000;
const SCHEMA_VERSION = '1.0.0';

export function ensureCacheDir() {
    if (!fs.existsSync(CACHE_DIR)) {
        fs.mkdirSync(CACHE_DIR, { recursive: true });
    }
}

export function hashVideoFile(videoPath, byteLimit = 64 * 1024) {
    if (!fs.existsSync(videoPath)) {
        throw new Error(`Video file not found: ${videoPath}`);
    }

    const stat = fs.statSync(videoPath);
    const readSize = Math.min(stat.size, byteLimit);

    const hash = crypto.createHash('sha256');
    const fd = fs.openSync(videoPath, 'r');
    const buffer = Buffer.alloc(readSize);
    fs.readSync(fd, buffer, 0, readSize, 0);
    fs.closeSync(fd);

    hash.update(buffer);
    hash.update(`|${stat.size}|${stat.mtimeMs}`);

    return hash.digest('hex');
}

export function getCacheKey(videoPath, options = {}) {
    const videoHash = hashVideoFile(videoPath);
    const prefix = videoHash.substring(0, 16);
    const schemaVersion = options.schemaVersion || SCHEMA_VERSION;
    const sampleMode = options.sampleMode || 'full';
    const maxDuration = options.maxDuration || null;

    return `blueprint_${prefix}_${schemaVersion}_${sampleMode}_${maxDuration || 'full'}`;
}

export function getCacheInfo(videoPath, options = {}) {
    ensureCacheDir();
    const key = getCacheKey(videoPath, options);
    const cacheFile = path.join(CACHE_DIR, `${key}.json`);

    if (!fs.existsSync(cacheFile)) {
        return { hit: false, key, file: cacheFile };
    }

    try {
        const content = fs.readFileSync(cacheFile, 'utf-8');
        const cached = JSON.parse(content);
        const age = Date.now() - cached.timestamp;
        const ageMinutes = Math.round(age / 60000);

        if (age > CACHE_EXPIRY_MS) {
            return { hit: false, key, file: cacheFile, expired: true, age_minutes: ageMinutes };
        }

        return {
            hit: true,
            key,
            file: cacheFile,
            age_minutes: ageMinutes,
            expires_in_minutes: Math.round((CACHE_EXPIRY_MS - age) / 60000),
            video_hash: cached.video_hash,
            video_size: cached.video_size,
        };
    } catch {
        return { hit: false, key, file: cacheFile, corrupted: true };
    }
}

export function getCached(key, type = 'blueprint') {
    ensureCacheDir();
    const cacheFile = path.join(CACHE_DIR, `${type}_${key}.json`);

    if (!fs.existsSync(cacheFile)) return null;

    try {
        const content = fs.readFileSync(cacheFile, 'utf-8');
        const cached = JSON.parse(content);
        const age = Date.now() - cached.timestamp;

        if (age > CACHE_EXPIRY_MS) {
            fs.unlinkSync(cacheFile);
            return null;
        }

        return cached.data;
    } catch {
        return null;
    }
}

export function getCachedByPath(videoPath, options = {}) {
    ensureCacheDir();
    const info = getCacheInfo(videoPath, options);

    if (!info.hit) return null;

    try {
        const content = fs.readFileSync(info.file, 'utf-8');
        const cached = JSON.parse(content);
        return cached.data;
    } catch {
        return null;
    }
}

export function setCache(videoPath, data, options = {}) {
    ensureCacheDir();
    const key = getCacheKey(videoPath, options);
    const cacheFile = path.join(CACHE_DIR, `${key}.json`);

    try {
        const stat = fs.statSync(videoPath);
        const videoHash = hashVideoFile(videoPath);

        fs.writeFileSync(cacheFile, JSON.stringify({
            timestamp: Date.now(),
            video_hash: videoHash,
            video_size: stat.size,
            video_path: videoPath,
            schema_version: options.schemaVersion || SCHEMA_VERSION,
            sample_mode: options.sampleMode || 'full',
            max_duration: options.maxDuration || null,
            data,
        }, null, 2));

        return { key, file: cacheFile };
    } catch (e) {
        console.warn(`Cache write failed: ${e.message}`);
        return null;
    }
}

export function clearCache(type = null) {
    ensureCacheDir();

    if (type) {
        const files = fs.readdirSync(CACHE_DIR).filter(f => f.startsWith(`${type}_`));
        for (const file of files) {
            fs.unlinkSync(path.join(CACHE_DIR, file));
        }
    } else {
        const files = fs.readdirSync(CACHE_DIR);
        for (const file of files) {
            fs.unlinkSync(path.join(CACHE_DIR, file));
        }
    }
}

export function getCacheStats() {
    ensureCacheDir();
    const files = fs.readdirSync(CACHE_DIR);

    const stats = {
        total: files.length,
        total_size_bytes: 0,
        byType: {},
        entries: [],
    };

    for (const file of files) {
        const filePath = path.join(CACHE_DIR, file);
        const stat = fs.statSync(filePath);
        stats.total_size_bytes += stat.size;

        const [type] = file.split('_');
        stats.byType[type] = (stats.byType[type] || 0) + 1;

        try {
            const content = fs.readFileSync(filePath, 'utf-8');
            const cached = JSON.parse(content);
            const age = Date.now() - cached.timestamp;
            stats.entries.push({
                file,
                age_minutes: Math.round(age / 60000),
                expired: age > CACHE_EXPIRY_MS,
                video_hash: cached.video_hash?.substring(0, 16),
                video_size: cached.video_size,
            });
        } catch {
            stats.entries.push({ file, corrupted: true });
        }
    }

    return stats;
}
