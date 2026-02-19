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
