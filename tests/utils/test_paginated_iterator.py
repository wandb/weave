import gc
import weakref
from collections.abc import Iterator

import pytest

from weave.utils.paginated_iterator import PaginatedIterator

pytestmark = pytest.mark.trace_server


def _fetch_numbers(offset: int, limit: int) -> list[int]:
    numbers = [0, 1, 2, 3, 4]
    return numbers[offset : offset + limit]


def test_paginated_iterator_implements_iterator_protocol() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2)

    assert isinstance(paginated, Iterator)
    assert next(paginated) == 0
    assert next(paginated) == 1


def test_paginated_iterator_next_stops_at_end() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2, limit=3)

    assert next(paginated) == 0
    assert next(paginated) == 1
    assert next(paginated) == 2
    with pytest.raises(StopIteration):
        next(paginated)


def test_paginated_iterator_iter_remains_restartable() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2)

    assert next(paginated) == 0
    assert list(paginated) == [0, 1, 2, 3, 4]
    assert list(paginated) == [0, 1, 2, 3, 4]


def test_paginated_iterator_reuses_fetched_pages_within_instance() -> None:
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


def test_paginated_iterator_released_when_unreferenced() -> None:
    # Regression: a method-level functools.lru_cache keys on `self` and lives
    # for the process lifetime, pinning every iterator (and its fetched pages)
    # in memory. The per-instance cache must let the iterator be garbage
    # collected once the caller drops it.
    def fetch(offset: int, limit: int) -> list[int]:
        return list(range(100))[offset : offset + limit]

    paginated = PaginatedIterator(fetch, page_size=10)
    assert paginated[0] == 0  # populate the page cache

    ref = weakref.ref(paginated)
    del paginated
    gc.collect()

    assert ref() is None
