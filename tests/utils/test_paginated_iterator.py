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


def test_repr_without_size_func_has_no_length() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2)

    assert repr(paginated) == "<PaginatedIterator>"


def test_repr_shows_unknown_length_until_len_is_called() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2, size_func=lambda: 5)

    assert repr(paginated) == "<PaginatedIterator len=?>"


def test_len_populates_cache_and_repr_reflects_it() -> None:
    call_count = 0

    def size_func() -> int:
        nonlocal call_count
        call_count += 1
        return 5

    paginated = PaginatedIterator(_fetch_numbers, page_size=2, size_func=size_func)

    assert len(paginated) == 5
    assert call_count == 1
    assert repr(paginated) == "<PaginatedIterator len=5>"


def test_len_is_cached_across_calls() -> None:
    call_count = 0

    def size_func() -> int:
        nonlocal call_count
        call_count += 1
        return 42

    paginated = PaginatedIterator(_fetch_numbers, page_size=2, size_func=size_func)

    assert len(paginated) == 42
    assert len(paginated) == 42
    assert len(paginated) == 42
    assert call_count == 1


def test_repr_does_not_trigger_size_func() -> None:
    call_count = 0

    def size_func() -> int:
        nonlocal call_count
        call_count += 1
        return 5

    paginated = PaginatedIterator(_fetch_numbers, page_size=2, size_func=size_func)

    repr(paginated)
    repr(paginated)
    assert call_count == 0


def test_len_without_size_func_raises() -> None:
    paginated = PaginatedIterator(_fetch_numbers, page_size=2)

    with pytest.raises(TypeError):
        len(paginated)
