import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';
import * as fs from 'fs';

const __root = resolve(dirname(fileURLToPath(import.meta.url)), '..');

export function getRoot() {
    return __root;
}

export function getSrcPath(filename = '') {
    return resolve(__root, 'src', filename);
}

export function getConfigPath(filename) {
    return resolve(__root, 'config', filename);
}

export function getUtilsPath(filename = '') {
    return resolve(__root, 'utils', filename);
}

export function getOutputPath(filename = '') {
    const envPath = process.env.VIDEO_REV_OUTPUT_DIR || resolve(__root, 'output_blueprints');
    return resolve(envPath, filename);
}

export function getCachePath(filename = '') {
    return resolve(__root, '.cache', filename);
}

export function resolveTemplate(templateName) {
    const templatePath = getConfigPath(templateName);
    if (!fs.existsSync(templatePath)) {
        throw new Error(`Template not found: ${templatePath}`);
    }
    return JSON.parse(fs.readFileSync(templatePath, 'utf-8'));
}

export function normalizeForEnv(target) {
    const platform = process.platform;

    if (typeof target !== 'string') return target;
    if (target.includes('://')) return target;

    const isUNC = target.startsWith('\\\\');
    if (isUNC) {
        const uncPath = target.replace(/\\\\/g, '/').replace(/\\/g, '/');
        const parts = uncPath.split('/').filter(Boolean);
        if (parts.length >= 2) {
            return `/mnt/${parts[0].toLowerCase()}/${parts.slice(1).join('/')}`;
        }
    }

    const isWindowsPath = /^[a-zA-Z]:[\\/]/.test(target);
    if (isWindowsPath) {
        const drive = target[0].toLowerCase();
        const posixPath = target.slice(2).replace(/\\/g, '/').replace(/^\/+/, '');
        return `/mnt/${drive}/${posixPath}`;
    }

    return resolve(target);
}

export default {
    getRoot,
    getSrcPath,
    getConfigPath,
    getUtilsPath,
    getOutputPath,
    getCachePath,
    resolveTemplate,
    normalizeForEnv,
};