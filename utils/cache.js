import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';

const __dirname = path.dirname(new URL(import.meta.url).pathname);
const CACHE_DIR = path.join(__dirname, '..', '.cache');

export function ensureCacheDir() {
    if (!fs.existsSync(CACHE_DIR)) {
        fs.mkdirSync(CACHE_DIR, { recursive: true });
    }
}

export function getCacheKey(data) {
    const hash = crypto.createHash('md5');
    hash.update(JSON.stringify(data));
    return hash.digest('hex');
}

export function getCached(key, type = 'blueprint') {
    ensureCacheDir();
    const cacheFile = path.join(CACHE_DIR, `${type}_${key}.json`);
    
    if (!fs.existsSync(cacheFile)) return null;
    
    try {
        const content = fs.readFileSync(cacheFile, 'utf-8');
        const cached = JSON.parse(content);
        const age = Date.now() - cached.timestamp;
        const maxAge = 24 * 60 * 60 * 1000;
        
        if (age > maxAge) {
            fs.unlinkSync(cacheFile);
            return null;
        }
        
        return cached.data;
    } catch {
        return null;
    }
}

export function setCache(key, data, type = 'blueprint') {
    ensureCacheDir();
    const cacheFile = path.join(CACHE_DIR, `${type}_${key}.json`);
    
    try {
        fs.writeFileSync(cacheFile, JSON.stringify({
            timestamp: Date.now(),
            data,
        }, null, 2));
    } catch (e) {
        console.warn(`Cache write failed: ${e.message}`);
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
        byType: {},
    };
    
    for (const file of files) {
        const [type] = file.split('_');
        stats.byType[type] = (stats.byType[type] || 0) + 1;
    }
    
    return stats;
}