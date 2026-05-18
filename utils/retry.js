export const RETRY_CONFIG = {
    maxRetries: 3,
    baseDelay: 1000,
    maxDelay: 30000,
    exponentialBase: 2,
    jitterFactor: 0.1,
};

export class RetriableError extends Error {
    constructor(message, statusCode = null) {
        super(message);
        this.name = 'RetriableError';
        this.statusCode = statusCode;
        this.isRetriable = isRetriableError(message, statusCode);
    }
}

export function isRetriableError(error, statusCode = null) {
    if (statusCode) {
        return [429, 500, 502, 503, 504].includes(statusCode);
    }

    const message = (error?.message || '').toLowerCase();
    const retriablePatterns = [
        'rate limit',
        'quota exceeded',
        'too many requests',
        'service unavailable',
        'internal server error',
        'bad gateway',
        'gateway timeout',
        'timeout',
        'connection reset',
        'network error',
        'econnreset',
        'econnrefused',
        'socket hang up',
    ];

    return retriablePatterns.some(pattern => message.includes(pattern));
}

export function calculateDelay(attempt, config = RETRY_CONFIG) {
    const exponentialDelay = config.baseDelay * Math.pow(config.exponentialBase, attempt - 1);
    const cappedDelay = Math.min(exponentialDelay, config.maxDelay);
    const jitter = cappedDelay * config.jitterFactor * Math.random();
    return Math.floor(cappedDelay + jitter);
}

export async function withRetry(fn, options = {}) {
    const config = { ...RETRY_CONFIG, ...options };
    let lastError;

    for (let attempt = 1; attempt <= config.maxRetries + 1; attempt++) {
        try {
            return await fn();
        } catch (error) {
            lastError = error;
            const isRetriable = error instanceof RetriableError ? error.isRetriable : isRetriableError(error, error?.statusCode);

            if (!isRetriable || attempt > config.maxRetries) {
                throw error;
            }

            const delay = calculateDelay(attempt, config);
            console.log(`   ↻ Retry ${attempt}/${config.maxRetries} in ${(delay / 1000).toFixed(1)}s...`);

            await sleep(delay);
        }
    }

    throw lastError;
}

export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

export function parseRetryArgs(args) {
    const result = {
        maxRetries: RETRY_CONFIG.maxRetries,
        force: false,
    };

    for (let i = 0; i < args.length; i++) {
        if (args[i] === '--max-retries' || args[i] === '-r') {
            const val = parseInt(args[i + 1], 10);
            if (!isNaN(val) && val >= 0) {
                result.maxRetries = val;
                i++;
            }
        } else if (args[i] === '--force' || args[i] === '-f') {
            result.force = true;
        }
    }

    return result;
}