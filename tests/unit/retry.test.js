import { withRetry, RETRY_CONFIG, calculateDelay, isRetriableError } from '../utils/retry.js';
import { describe, it, expect } from './test-framework.js';

describe('calculateDelay', () => {
    it('should increase delay with attempts', () => {
        const delay1 = calculateDelay(1);
        const delay2 = calculateDelay(2);
        const delay3 = calculateDelay(3);

        expect(delay2).toBeGreaterThan(delay1);
        expect(delay3).toBeGreaterThan(delay2);
    });

    it('should not exceed max delay', () => {
        const maxDelay = calculateDelay(10);
        expect(maxDelay).toBeLessThanOrEqual(RETRY_CONFIG.maxDelay * 1.1);
    });
});

describe('isRetriableError', () => {
    it('should detect rate limit errors', () => {
        expect(isRetriableError(new Error('Rate limit exceeded'), 429)).toBe(true);
    });

    it('should detect server errors', () => {
        expect(isRetriableError(new Error('Server error'), 500)).toBe(true);
        expect(isRetriableError(new Error('Internal error'), 503)).toBe(true);
    });

    it('should detect network errors', () => {
        expect(isRetriableError(new Error('connection reset'))).toBe(true);
        expect(isRetriableError(new Error('timeout'))).toBe(true);
    });
});

describe('withRetry', () => {
    it('should succeed on first try', async () => {
        let attempts = 0;
        const fn = async () => {
            attempts++;
            return 'success';
        };

        const result = await withRetry(fn, { maxRetries: 3 });
        expect(result).toBe('success');
        expect(attempts).toBe(1);
    });

    it('should retry on failure then succeed', async () => {
        let attempts = 0;
        const fn = async () => {
            attempts++;
            if (attempts < 3) {
                throw new Error('Temporary failure');
            }
            return 'success';
        };

        const result = await withRetry(fn, { maxRetries: 3 });
        expect(result).toBe('success');
        expect(attempts).toBe(3);
    });

    it('should fail after max retries', async () => {
        let attempts = 0;
        const fn = async () => {
            attempts++;
            throw new Error('Permanent failure');
        };

        try {
            await withRetry(fn, { maxRetries: 2 });
            expect(false).toBe(true);
        } catch (err) {
            expect(attempts).toBe(3);
        }
    });
});