import gc
import weakref
from collections.abc import Iterator

import pytest

from weave.utils.paginated_iterator import PaginatedIterator

pytestmark = pytest.mark.trace_server


def test_paginated_iterator_protocol_and_restart() -> None:
    # Implements the iterator protocol, yielding lazily across pages.
    paginated = PaginatedIterator(_fetch_numbers, page_size=2)
    assert isinstance(paginated, Iterator)
    assert next(paginated) == 0
    assert next(paginated) == 1

    # `next` stops at the configured limit.
    bounded = PaginatedIterator(_fetch_numbers, page_size=2, limit=3)
    assert next(bounded) == 0
    assert next(bounded) == 1
    assert next(bounded) == 2
    with pytest.raises(StopIteration):
        next(bounded)

    # `iter` is restartable even after a partial `next` consumption.
    restartable = PaginatedIterator(_fetch_numbers, page_size=2)
    assert next(restartable) == 0
    assert list(restartable) == [0, 1, 2, 3, 4]
    assert list(restartable) == [0, 1, 2, 3, 4]


def test_paginated_iterator_limit_bounds_index_and_slice_consistently() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2, limit=3)

    assert paginated[2] == 2
    with pytest.raises(IndexError):
        paginated[3]

    # Indexing, slicing, and iteration all agree on the limit boundary.
    assert paginated[0:10] == [0, 1, 2]
    assert paginated[:] == [0, 1, 2]
    assert list(paginated) == [0, 1, 2]


def test_paginated_iterator_per_instance_cache_reuses_and_releases() -> None:
    fetch_offsets: list[int] = []

    def fetch(offset: int, limit: int) -> list[int]:
        fetch_offsets.append(offset)
        return list(range(100))[offset : offset + limit]

    paginated = PaginatedIterator(fetch, page_size=10)

    # Two reads within the same page hit the source exactly once.
    assert paginated[0] == 0
    assert paginated[9] == 9
    assert fetch_offsets == [0]

    # A read in a different page triggers exactly one more fetch.
    assert paginated[10] == 10
    assert fetch_offsets == [0, 10]

    # The per-instance cache must not pin the iterator: dropping the only
    # reference lets it (and its fetched pages) be garbage collected.
    ref = weakref.ref(paginated)
    del paginated
    gc.collect()
    assert ref() is None


def _fetch_numbers(offset: int, limit: int) -> list[int]:
    numbers = [0, 1, 2, 3, 4]
    return numbers[offset : offset + limit]
