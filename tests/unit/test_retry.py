import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tests.unit.test_framework import describe, expect, it
from utils.retry import RETRY_CONFIG, _is_retriable_error, calculate_delay, extract_status_code, with_retry


def run_tests():
    def _test_default_max_retries():
        expect(RETRY_CONFIG["maxRetries"]).to_be(3)
        expect(RETRY_CONFIG["baseDelay"]).to_be(2000)
        expect(RETRY_CONFIG["maxDelay"]).to_be(60000)

    describe("RETRY_CONFIG", lambda: it("default maxRetries is 3", _test_default_max_retries))

    def _test_delay_increases():
        delay1 = calculate_delay(1)
        delay2 = calculate_delay(2)
        delay3 = calculate_delay(3)
        expect(delay2).to_be_greater_than(delay1)
        expect(delay3).to_be_greater_than(delay2)

    describe('calculateDelay', lambda: it('should increase delay with attempts', _test_delay_increases))

    def _test_max_delay():
        max_delay = calculate_delay(10)
        expect(max_delay).to_be_less_than_or_equal(RETRY_CONFIG['maxDelay'] * 1.1)

    describe('calculateDelay', lambda: it('should not exceed max delay', _test_max_delay))

    def _test_rate_limit():
        expect(_is_retriable_error('Rate limit exceeded', 429)).to_be(True)

    describe('isRetriableError', lambda: it('should detect rate limit errors', _test_rate_limit))

    def _test_server_errors():
        expect(_is_retriable_error('Server error', 500)).to_be(True)
        expect(_is_retriable_error('Internal error', 503)).to_be(True)

    describe('isRetriableError', lambda: it('should detect server errors', _test_server_errors))

    def _test_network_errors():
        expect(_is_retriable_error('connection reset')).to_be(True)
        expect(_is_retriable_error('timeout')).to_be(True)

    describe('isRetriableError', lambda: it('should detect network errors', _test_network_errors))

    def _test_gemini_503_message():
        msg = "503 UNAVAILABLE. {'error': {'code': 503, 'message': 'high demand'}}"
        expect(extract_status_code(msg)).to_be(503)
        expect(_is_retriable_error(msg)).to_be(True)

    describe('isRetriableError', lambda: it('should detect Gemini 503 unavailable strings', _test_gemini_503_message))

    def _test_success_first_try():
        async def _run():
            attempts = [0]
            async def fn():
                attempts[0] += 1
                return 'success'
            result = await with_retry(fn, {'maxRetries': 3})
            expect(result).to_be('success')
            expect(attempts[0]).to_be(1)
        asyncio.run(_run())

    describe('withRetry', lambda: it('should succeed on first try', _test_success_first_try))

    def _test_retry_then_succeed():
        async def _run():
            attempts = [0]
            async def fn():
                attempts[0] += 1
                if attempts[0] < 3:
                    raise RuntimeError('rate limit exceeded')
                return 'success'
            result = await with_retry(fn, {'maxRetries': 3})
            expect(result).to_be('success')
            expect(attempts[0]).to_be(3)
        asyncio.run(_run())

    describe('withRetry', lambda: it('should retry on failure then succeed', _test_retry_then_succeed))

    def _test_fail_after_max_retries():
        async def _run():
            attempts = [0]
            async def fn():
                attempts[0] += 1
                raise RuntimeError('rate limit exceeded')
            try:
                await with_retry(fn, {'maxRetries': 2})
                expect(False).to_be(True)
            except RuntimeError:
                expect(attempts[0]).to_be(3)
        asyncio.run(_run())

    describe('withRetry', lambda: it('should fail after max retries', _test_fail_after_max_retries))
