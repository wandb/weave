from .. import safe_cache
from .. import context_state


class Counter:
    def __init__(self, id):
        self.id = id
        self.count = 0

    def add(self, v):
        self.count += 1
        return self.id + v


def test_safe_cache_caches():
    counter1 = Counter(1)

    @safe_cache.safe_lru_cache(10)
    def add1(a):
        return counter1.add(a)

    assert add1(1) == 2
    assert add1(1) == 2
    assert counter1.count == 1
    assert add1(2) == 3
    assert counter1.count == 2


def test_safe_is_namespaced():
    counter = Counter(1)

    @safe_cache.safe_lru_cache(10)
    def add1(a):
        return counter.add(a)

    with context_state.cache_namespace("x"):
        assert add1(1) == 2
    assert counter.count == 1
    with context_state.cache_namespace("y"):
        assert add1(1) == 2
    assert counter.count == 2
    with context_state.cache_namespace("x"):
        assert add1(1) == 2
    assert counter.count == 2
