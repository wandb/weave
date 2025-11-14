"""Utility class for iterating over data with pagination."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import TYPE_CHECKING, Generic, Protocol, overload

from typing_extensions import TypeVar

if TYPE_CHECKING:
    import pandas as pd

T = TypeVar("T")
R = TypeVar("R", covariant=True)


class FetchFunc(Protocol[T]):
    def __call__(self, offset: int, limit: int) -> list[T]: ...


TransformFunc = Callable[[T], R]
SizeFunc = Callable[[], int]


class PaginatedIterator(Generic[T, R]):
    """An iterator that fetches pages of items from a server and optionally transforms them
    into a more user-friendly type.
    """

    def __init__(
        self,
        fetch_func: FetchFunc[T],
        page_size: int = 1000,
        transform_func: TransformFunc[T, R] | None = None,
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
    def _get_one(self: PaginatedIterator[T, R], index: int) -> R: ...
    def _get_one(self, index: int) -> T | R:
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
    def _get_slice(self: PaginatedIterator[T, R], key: slice) -> Iterator[R]: ...
    def _get_slice(self, key: slice) -> Iterator[T] | Iterator[R]:
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
    def __getitem__(self: PaginatedIterator[T, R], key: int) -> R: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, T], key: slice) -> list[T]: ...
    @overload
    def __getitem__(self: PaginatedIterator[T, R], key: slice) -> list[R]: ...
    def __getitem__(self, key: slice | int) -> T | R | list[T] | list[R]:
        if isinstance(key, slice):
            return list(self._get_slice(key))
        return self._get_one(key)

    @overload
    def __iter__(self: PaginatedIterator[T, T]) -> Iterator[T]: ...
    @overload
    def __iter__(self: PaginatedIterator[T, R]) -> Iterator[R]: ...
    def __iter__(self) -> Iterator[T] | Iterator[R]:
        return self._get_slice(slice(0, None, 1))

    def __len__(self) -> int:
        """This method is included for convenience.  It includes a network call, which
        is typically slower than most other len() operations!
        """
        if not self.size_func:
            raise TypeError("This iterator does not support len()")
        return self.size_func()

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
