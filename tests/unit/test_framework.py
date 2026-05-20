import sys
import traceback


class TestResult:
    def __init__(self, name, passed, error=None):
        self.name = name
        self.passed = passed
        self.error = error


class Expect:
    def __init__(self, actual):
        self.actual = actual

    def to_be(self, expected):
        if self.actual != expected:
            raise AssertionError(f'Expected {expected!r}, got {self.actual!r}')

    def to_be_greater_than(self, expected):
        if self.actual <= expected:
            raise AssertionError(f'Expected > {expected!r}, got {self.actual!r}')

    def to_be_less_than_or_equal(self, expected):
        if self.actual > expected:
            raise AssertionError(f'Expected <= {expected!r}, got {self.actual!r}')

    def to_be_defined(self):
        if self.actual is None:
            raise AssertionError('Expected defined, got None')

    def to_be_undefined(self):
        if self.actual is not None:
            raise AssertionError(f'Expected None, got {self.actual!r}')

    def to_be_truthy(self):
        if not self.actual:
            raise AssertionError(f'Expected truthy, got {self.actual!r}')

    def to_be_falsy(self):
        if self.actual:
            raise AssertionError(f'Expected falsy, got {self.actual!r}')

    def to_be_instance(self, cls):
        if not isinstance(self.actual, cls):
            raise AssertionError(f'Expected isinstance({cls.__name__}), got {type(self.actual).__name__}')

    def to_contain(self, item):
        if item not in self.actual:
            raise AssertionError(f'Expected {self.actual!r} to contain {item!r}')

    def to_equal(self, expected):
        if self.actual != expected:
            raise AssertionError(f'Expected {expected!r}, got {self.actual!r}')


def expect(actual):
    return Expect(actual)


_results = []


def describe(name, fn):
    print(f'  {name}')
    fn()


def it(name, fn):
    try:
        result = fn()
        if hasattr(result, '__await__'):
            import asyncio
            asyncio.get_event_loop().run_until_complete(result)
        print(f'    ✅ {name}')
        _results.append(TestResult(name, True))
    except Exception as err:
        print(f'    ❌ {name}')
        print(f'       Error: {err}')
        _results.append(TestResult(name, False, str(err)))
        raise


def get_results():
    return _results


def print_summary():
    total = len(_results)
    passed = sum(1 for r in _results if r.passed)
    failed = total - passed

    print()
    print('═' * 60)
    print(f'  Results: {passed}/{total} passed', flush=True)
    if failed > 0:
        print(f'  Failed: {failed}', flush=True)
        for r in _results:
            if not r.passed:
                print(f'    ❌ {r.name}: {r.error}', flush=True)
    print('═' * 60)

    return failed == 0


def run_all(test_modules):
    for module in test_modules:
        module_name = module.__name__.split('.')[-1]
        print(f'\n── {module_name} ──\n', flush=True)
        try:
            if hasattr(module, 'run_tests'):
                module.run_tests()
        except Exception:
            pass
    return print_summary()
