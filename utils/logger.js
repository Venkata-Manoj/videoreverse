import * as fs from 'fs';
import * as path from 'path';
import { getOutputPath } from '../src/path-resolver.js';

const LOG_DIR = getOutputPath();
const ERROR_LOG_PATH = path.join(LOG_DIR, 'errors.log');

export const LogLevel = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3,
    QUIET: 4,
};

let currentLogLevel = LogLevel.INFO;

export function setLogLevel(level) {
    if (typeof level === 'string') {
        switch (level.toLowerCase()) {
            case 'debug':
                currentLogLevel = LogLevel.DEBUG;
                break;
            case 'info':
                currentLogLevel = LogLevel.INFO;
                break;
            case 'warn':
                currentLogLevel = LogLevel.WARN;
                break;
            case 'error':
                currentLogLevel = LogLevel.ERROR;
                break;
            case 'quiet':
            case 'silent':
                currentLogLevel = LogLevel.QUIET;
                break;
            default:
                currentLogLevel = LogLevel.INFO;
        }
    } else {
        currentLogLevel = level;
    }
}

export function getLogLevel() {
    return currentLogLevel;
}

export function shouldLog(level) {
    return level >= currentLogLevel;
}

function formatTimestamp() {
    return new Date().toISOString();
}

function ensureLogDir() {
    if (!fs.existsSync(LOG_DIR)) {
        fs.mkdirSync(LOG_DIR, { recursive: true });
    }
}

export function log(level, category, message, data = null) {
    if (!shouldLog(level)) return;

    const timestamp = formatTimestamp();
    const levelNames = ['DEBUG', 'INFO', 'WARN', 'ERROR'];
    const levelName = levelNames[level] || 'UNKNOWN';

    const formatted = `[${timestamp}] [${levelName}] [${category}] ${message}`;

    if (level >= LogLevel.ERROR) {
        console.error(formatted);
    } else {
        console.log(formatted);
    }

    if (data) {
        const dataStr = typeof data === 'object' ? JSON.stringify(data, null, 2) : String(data);
        console.log(dataStr);
    }

    if (level >= LogLevel.ERROR) {
        appendToErrorLog(formatted, data);
    }
}

export function debug(category, message, data = null) {
    log(LogLevel.DEBUG, category, message, data);
}

export function info(category, message, data = null) {
    log(LogLevel.INFO, category, message, data);
}

export function warn(category, message, data = null) {
    log(LogLevel.WARN, category, message, data);
}

export function error(category, message, data = null) {
    log(LogLevel.ERROR, category, message, data);
}

export function appendToErrorLog(message, data = null) {
    ensureLogDir();

    try {
        let logEntry = message;
        if (data) {
            logEntry += '\n  Data: ' + (typeof data === 'object' ? JSON.stringify(data) : String(data));
        }
        logEntry += '\n';

        fs.appendFileSync(ERROR_LOG_PATH, logEntry);
    } catch (err) {
        console.error('Failed to write to error log:', err.message);
    }
}

export function getErrorLog() {
    ensureLogDir();

    if (!fs.existsSync(ERROR_LOG_PATH)) {
        return [];
    }

    try {
        const content = fs.readFileSync(ERROR_LOG_PATH, 'utf-8');
        return content.split('\n').filter(line => line.trim());
    } catch {
        return [];
    }
}

export function clearErrorLog() {
    ensureLogDir();

    if (fs.existsSync(ERROR_LOG_PATH)) {
        fs.unlinkSync(ERROR_LOG_PATH);
    }
}

export function logPipelineStep(stepName, duration, success = true, error = null) {
    const entry = {
        timestamp: formatTimestamp(),
        step: stepName,
        duration_ms: duration,
        success,
        error: error?.message || null,
    };

    ensureLogDir();

    const logFile = path.join(LOG_DIR, 'pipeline_history.jsonl');
    try {
        fs.appendFileSync(logFile, JSON.stringify(entry) + '\n');
    } catch (err) {
        console.error('Failed to write pipeline history:', err.message);
    }

    return entry;
}