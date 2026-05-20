"""Utility class for iterating over data with pagination."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Generic, Protocol, overload

from typing_extensions import TypeVar

if TYPE_CHECKING:
    import pandas as pd

T = TypeVar("T")
R_co = TypeVar("R_co", covariant=True)

DEFAULT_PAGE_SIZE = 1000


class FetchFunc(Protocol[T]):
    def __call__(self, offset: int, limit: int) -> list[T]: ...


TransformFunc = Callable[[T], R_co]
SizeFunc = Callable[[], int]


class PaginatedIterator(Generic[T, R_co]):
    """An iterator that fetches pages of items from a server and optionally transforms them
    into a more user-friendly type.
    """

    def __init__(
        self,
        fetch_func: FetchFunc[T],
        page_size: int = DEFAULT_PAGE_SIZE,
        transform_func: TransformFunc[T, R_co] | None = None,
        size_func: SizeFunc | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> None:
        self.fetch_func = fetch_func
        self.page_size = page_size
        self.transform_func = transform_func
        self.size_func = size_func
        self.limit = limit
        self.offset = offset
        self._next_index = 0
        self._cached_size: int | None = None

        if page_size <= 0:
            raise ValueError("page_size must be greater than 0")
        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than 0")

    @lru_cache  # noqa: B019
    def _fetch_page(self, index: int) -> list[T]:
        return self.fetch_func(index * self.page_size, self.page_size)

    @overload
    def _get_one(self: PaginatedIterator[T, T], index: int) -> T: ...
    @overload
    def _get_one(self: PaginatedIterator[T, R_co], index: int) -> R_co: ...
    def _get_one(self, index: int) -> T | R_co:
        if index < 0:
            raise IndexError("Negative indexing not supported")

        if self.limit is not None and index >= self.limit + (self.offset or 0):
            raise IndexError(f"Index {index} out of range")

        if self.offset is not None:
            index += self.offset

        page_index = index // self.page_size
        page_offset = index % self.page_size

        page = self._fetch_page(page_index)
        if page_offset >= len(page):
            raise IndexError(f"Index {index} out of range")

        res = page[page_offset]
        if transform := self.transform_func:
            return transform(res)
        return res

    @overload
    def _get_slice(self: PaginatedIterator[T, T], key: slice) -> Iterator[T]: ...
    @overload
    def _get_slice(self: PaginatedIterator[T, R_co], key: slice) -> Iterator[R_co]: ...
    def _get_slice(self, key: slice) -> Iterator[T] | Iterator[R_co]:
        if (start := key.start or 0) < 0:
            raise ValueError("Negative start not supported")
        if (stop := key.stop) is not None and stop < 0:
            raise ValueError("Negative stop not supported")
        if (step := key.step or 1) < 0:
            raise ValueError("Negative step not supported")

        # Apply limit if provided
        if self.limit is not None and (stop is None or stop > self.limit):
            stop = self.limit

        # Apply offset if provided
        if self.offset is not None:
            start += self.offset
            if stop is not None:
                stop += self.offset

        i = start
        while stop is None or i < stop:
            try:
                yield self._get_one(i)
            except IndexError:
                break
            i += step

    @overload
    def __getitem__(self: PaginatedIterator[T, T], key: int) -> T: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, R_co], key: int) -> R_co: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, T], key: slice) -> list[T]: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, R_co], key: slice) -> list[R_co]: ...
    def __getitem__(self, key: slice | int) -> T | R_co | list[T] | list[R_co]:
        if isinstance(key, slice):
            return list(self._get_slice(key))
        return self._get_one(key)

    @overload
    def __iter__(self: PaginatedIterator[T, T]) -> Iterator[T]: ...
    @overload
    def __iter__(self: PaginatedIterator[T, R_co]) -> Iterator[R_co]: ...
    def __iter__(self) -> Iterator[T] | Iterator[R_co]:
        return self._get_slice(slice(0, None, 1))

    @overload
    def __next__(self: PaginatedIterator[T, T]) -> T: ...
    @overload
    def __next__(self: PaginatedIterator[T, R_co]) -> R_co: ...
    def __next__(self) -> T | R_co:
        try:
            item = self._get_one(self._next_index)
        except IndexError as exc:
            raise StopIteration from exc
        self._next_index += 1
        return item

    def __len__(self) -> int:
        """This method is included for convenience.  The first call issues a
        network request to fetch the count, which is typically slower than most
        other len() operations.  Subsequent calls are served from a cache.
        """
        if not self.size_func:
            raise TypeError("This iterator does not support len()")
        if self._cached_size is None:
            self._cached_size = self.size_func()
        return self._cached_size

    def __repr__(self) -> str:
        # Deliberately does NOT call size_func: repr must be cheap and free of
        # side effects (Jupyter, debuggers, tracebacks, and %r in log lines all
        # invoke repr).  We only surface the count if len() has already
        # populated the cache.
        name = type(self).__name__
        if self.size_func is None:
            return f"<{name}>"
        size = self._cached_size if self._cached_size is not None else "?"
        return f"<{name} len={size}>"

    def to_pandas(self) -> pd.DataFrame:
        """Convert the iterator's contents to a pandas DataFrame.

        Returns:
            A pandas DataFrame containing all the data from the iterator.

        Example:
            ```python
            calls = client.get_calls()
            df = calls.to_pandas()
            ```

        Note:
            This method will fetch all data from the iterator, which may involve
            multiple network calls. For large datasets, consider using limits
            or filters to reduce the amount of data fetched.
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to use this method") from None

        records = []
        for item in self:
            if isinstance(item, dict):
                records.append(item)
            elif hasattr(item, "to_dict"):
                records.append(item.to_dict())
            else:
                raise ValueError(f"Unable to convert item to dict: {item}")

        return pd.DataFrame(records)
