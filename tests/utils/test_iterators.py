import threading

import pytest

from weave.utils.iterators import ThreadSafeLazyList, first


def _gen():
    yield 10
    yield 20
    yield 30


class _CustomIterable:
    def __iter__(self):
        return iter([99, 88, 77])


@pytest.mark.parametrize(
    ("iterable", "expected"),
    [
        ([1, 2, 3], 1),
        ([42], 42),
        (["a", "b", "c"], "a"),
        ("hello", "h"),
        ("x", "x"),
        (range(5), 0),
        (range(10, 20), 10),
        (range(100, 101), 100),
        (_gen(), 10),
        (iter([7, 8, 9]), 7),
        (iter("abc"), "a"),
        ({42}, 42),
        ((100, 200, 300), 100),
        (("x",), "x"),
        (_CustomIterable(), 99),
    ],
)
def test_first_returns_first_element(iterable, expected):
    """first() yields the first element across list/str/range/generator/iterator/set/tuple/custom."""
    assert first(iterable) == expected


@pytest.mark.parametrize("empty", [[], "", range(0), iter([])])
def test_first_empty_raises(empty):
    """first() on an empty iterable raises StopIteration."""
    with pytest.raises(StopIteration):
        first(empty)


def test_lazy_list_sequence_access():
    """len, indexing, negative index, slicing, and full iteration over a fresh list."""
    iterator = ThreadSafeLazyList(iter(range(10)))

    assert len(iterator) == 10
    assert iterator[0] == 0
    assert iterator[5] == 5
    assert iterator[9] == 9
    assert iterator[-1] == 9
    assert iterator[1:3] == [1, 2]
    assert iterator[2:5] == [2, 3, 4]
    assert iterator[:3] == [0, 1, 2]
    assert iterator[7:] == [7, 8, 9]
    assert iterator[::2] == [0, 2, 4, 6, 8]
    assert iterator[::-1] == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert list(iterator) == list(range(10))


def test_lazy_list_repeated_iteration():
    """Repeated iteration returns the same data each time."""
    data = list(range(5))
    iterator = ThreadSafeLazyList(iter(data))

    assert list(iterator) == data
    assert list(iterator) == data
    assert list(iterator) == data


def test_lazy_list_known_length():
    """known_length avoids exhausting the iterator while still allowing access."""
    iterator = ThreadSafeLazyList(iter(range(5)), known_length=5)
    assert len(iterator) == 5
    assert iterator[4] == 4


def test_lazy_list_empty():
    """Empty iterator: zero length, IndexError on access, empty materialization."""
    iterator = ThreadSafeLazyList(iter([]))
    assert len(iterator) == 0
    with pytest.raises(IndexError):
        _ = iterator[0]
    assert list(iterator) == []


def test_lazy_list_index_out_of_range():
    """Out-of-range index raises IndexError; iterator exhaustion is still materializable."""
    iterator = ThreadSafeLazyList(_CountingIterator())
    assert len(iterator) == 5
    with pytest.raises(IndexError):
        _ = iterator[10]
    assert list(iterator) == [0, 1, 2, 3, 4]


def test_lazy_list_concurrent_iteration():
    """Concurrent full iterations from multiple threads see identical data."""
    data = list(range(1000))
    iterator = ThreadSafeLazyList(iter(data))
    results = []

    def reader_thread():
        results.append(list(iterator))

    threads = [threading.Thread(target=reader_thread) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r == data for r in results)


def test_lazy_list_concurrent_mixed_operations():
    """Concurrent mixed reads/slices/iterations from multiple threads agree."""
    data = list(range(100))
    iterator = ThreadSafeLazyList(iter(data))
    results = []

    def mixed_ops_thread():
        local_results = [iterator[10], list(iterator[20:25]), iterator[50]]
        local_results.extend(iterator[90:])
        results.append(local_results)

    threads = [threading.Thread(target=mixed_ops_thread) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = [10, list(range(20, 25)), 50, *range(90, 100)]
    assert all(r == expected for r in results)


class _CountingIterator:
    def __init__(self):
        self.count = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.count < 5:
            self.count += 1
            return self.count - 1
        raise StopIteration
