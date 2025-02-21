import threading

import pytest

from weave.utils.iterators import ThreadSafeInMemoryIteratorAsSequence


def test_basic_sequence_operations():
    # Test basic sequence operations
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(range(10)))
    assert len(iterator) == 10
    assert iterator[0] == 0
    assert iterator[1:3] == [1, 2]
    assert list(iterator) == list(range(10))


def test_empty_iterator():
    # Test behavior with empty iterator
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter([]))
    assert len(iterator) == 0
    with pytest.raises(IndexError):
        _ = iterator[0]
    assert list(iterator) == []


def test_known_length():
    # Test initialization with known length
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(range(5)), known_length=5)
    assert len(iterator) == 5  # Should not need to exhaust iterator
    assert iterator[4] == 4  # Access last element


def test_multiple_iterations():
    # Test multiple iterations return same results
    data = list(range(5))
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(data))

    assert list(iterator) == data  # First iteration
    assert list(iterator) == data  # Second iteration
    assert list(iterator) == data  # Third iteration


def test_concurrent_access():
    # Test thread-safe concurrent access
    data = list(range(1000))
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(data))
    results = []

    def reader_thread():
        results.append(list(iterator))

    threads = [threading.Thread(target=reader_thread) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should see the same data
    assert all(r == data for r in results)


def test_slicing():
    # Test various slicing operations
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(range(10)))

    assert iterator[2:5] == [2, 3, 4]
    assert iterator[:3] == [0, 1, 2]
    assert iterator[7:] == [7, 8, 9]
    assert iterator[::2] == [0, 2, 4, 6, 8]
    assert iterator[::-1] == [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]


def test_random_access():
    # Test random access patterns
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(range(10)))

    assert iterator[5] == 5  # Middle access
    assert iterator[1] == 1  # Earlier access
    assert iterator[8] == 8  # Later access
    assert iterator[0] == 0  # First element
    assert iterator[9] == 9  # Last element


def test_concurrent_mixed_operations():
    # Test concurrent mixed operations (reads, slices, iterations)
    data = list(range(100))
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(data))
    results = []

    def mixed_ops_thread():
        local_results = []
        local_results.append(iterator[10])  # Single element access
        local_results.append(list(iterator[20:25]))  # Slice access
        local_results.append(iterator[50])  # Another single element
        local_results.extend(iterator[90:])  # End slice
        results.append(local_results)

    threads = [threading.Thread(target=mixed_ops_thread) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify all threads got the same results
    expected = [10, list(range(20, 25)), 50, list(range(90, 100))]
    assert all(r == expected for r in results)


def test_index_out_of_range():
    # Test index out of range behavior
    iterator = ThreadSafeInMemoryIteratorAsSequence(iter(range(5)))

    with pytest.raises(IndexError):
        _ = iterator[10]

    assert iterator[-1] == 4  # Negative indices are supported


def test_iterator_exhaustion():
    # Test behavior when iterator is exhausted
    class CountingIterator:
        def __init__(self):
            self.count = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.count < 5:
                self.count += 1
                return self.count - 1
            raise StopIteration

    iterator = ThreadSafeInMemoryIteratorAsSequence(CountingIterator())

    # Access beyond iterator length should raise IndexError
    assert len(iterator) == 5
    with pytest.raises(IndexError):
        _ = iterator[10]

    # Verify original data is still accessible
    assert list(iterator) == [0, 1, 2, 3, 4]
