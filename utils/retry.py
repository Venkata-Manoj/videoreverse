import asyncio
import random

RETRY_CONFIG = {
    'maxRetries': 3,
    'baseDelay': 1000,
    'maxDelay': 30000,
    'exponentialBase': 2,
    'jitterFactor': 0.1,
}


class RetriableError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.name = 'RetriableError'
        self.status_code = status_code
        self.is_retriable = _is_retriable_error(message, status_code)


def _is_retriable_error(message, status_code=None):
    if status_code is not None:
        return status_code in [429, 500, 502, 503, 504]

    msg = (message or '').lower()
    retriable_patterns = [
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
    ]
    return any(pattern in msg for pattern in retriable_patterns)


def calculate_delay(attempt, config=None):
    if config is None:
        config = RETRY_CONFIG
    exponential_delay = config['baseDelay'] * (config['exponentialBase'] ** (attempt - 1))
    capped_delay = min(exponential_delay, config['maxDelay'])
    jitter = capped_delay * config['jitterFactor'] * random.random()
    return int(capped_delay + jitter)


async def with_retry(fn, options=None):
    if options is None:
        options = {}
    config = {**RETRY_CONFIG, **options}
    last_error = None

    for attempt in range(1, config['maxRetries'] + 2):
        try:
            result = fn()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except Exception as error:
            last_error = error
            is_retriable = isinstance(error, RetriableError) and error.is_retriable
            if not is_retriable:
                is_retriable = _is_retriable_error(str(error), getattr(error, 'status_code', None))

            if not is_retriable or attempt > config['maxRetries']:
                raise

            delay = calculate_delay(attempt, config)
            print(f'   ↻ Retry {attempt}/{config["maxRetries"]} in {(delay / 1000):.1f}s...', flush=True)
            await asyncio.sleep(delay / 1000)

    raise last_error


async def sleep(ms):
    await asyncio.sleep(ms / 1000)


def parse_retry_args(args):
    result = {
        'maxRetries': RETRY_CONFIG['maxRetries'],
        'force': False,
    }

    i = 0
    while i < len(args):
        if args[i] in ('--max-retries', '-r'):
            if i + 1 < len(args):
                try:
                    val = int(args[i + 1])
                    if val >= 0:
                        result['maxRetries'] = val
                    i += 1
                except ValueError:
                    pass
        elif args[i] in ('--force', '-f'):
            result['force'] = True
        i += 1

    return result
