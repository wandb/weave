"""Async streaming support for Weave, following OpenAI's pattern."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable, Generic, Optional, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class AsyncStream(Generic[T]):
    """Async stream implementation for handling streaming responses."""

    def __init__(
        self,
        iterator: AsyncIterator[T],
        *,
        cast_to: Optional[type[T]] = None,
        response: Optional[Any] = None,
    ):
        self._iterator = iterator
        self._cast_to = cast_to
        self.response = response
        self._has_started = False

    async def __aiter__(self) -> AsyncIterator[T]:
        """Async iteration support."""
        self._has_started = True
        async for item in self._iterator:
            if self._cast_to is not None:
                yield self._cast_to(item)
            else:
                yield item

    async def __anext__(self) -> T:
        """Get next item from stream."""
        if not self._has_started:
            self._has_started = True
        return await self._iterator.__anext__()

    @classmethod
    def from_list(cls, items: list[T]) -> AsyncStream[T]:
        """Create stream from a list of items."""
        async def _iter() -> AsyncIterator[T]:
            for item in items:
                yield item
        
        return cls(_iter())

    async def to_list(self) -> list[T]:
        """Convert stream to list."""
        items = []
        async for item in self:
            items.append(item)
        return items

    def map(self, func: Callable[[T], R]) -> AsyncStream[R]:
        """Map function over stream items."""
        async def _mapped_iter() -> AsyncIterator[R]:
            async for item in self:
                yield func(item)
        
        return AsyncStream(_mapped_iter())

    def filter(self, func: Callable[[T], bool]) -> AsyncStream[T]:
        """Filter stream items."""
        async def _filtered_iter() -> AsyncIterator[T]:
            async for item in self:
                if func(item):
                    yield item
        
        return AsyncStream(_filtered_iter())

    async def first(self) -> Optional[T]:
        """Get first item from stream."""
        try:
            async for item in self:
                return item
        except StopAsyncIteration:
            return None

    async def count(self) -> int:
        """Count items in stream."""
        count = 0
        async for _ in self:
            count += 1
        return count


class AsyncPaginator(Generic[T]):
    """Async paginator for handling paginated API responses."""

    def __init__(
        self,
        fetch_func: Callable[[int, int], AsyncIterator[T]],
        page_size: int = 100,
        limit: Optional[int] = None,
    ):
        self._fetch_func = fetch_func
        self._page_size = page_size
        self._limit = limit

    async def __aiter__(self) -> AsyncIterator[T]:
        """Iterate through all pages."""
        offset = 0
        total_yielded = 0
        
        while True:
            # Calculate how many items to fetch
            if self._limit is not None:
                remaining = self._limit - total_yielded
                if remaining <= 0:
                    break
                fetch_limit = min(self._page_size, remaining)
            else:
                fetch_limit = self._page_size
            
            # Fetch page
            page_count = 0
            async for item in self._fetch_func(offset, fetch_limit):
                yield item
                page_count += 1
                total_yielded += 1
                
                if self._limit is not None and total_yielded >= self._limit:
                    return
            
            # If we got fewer items than requested, we've reached the end
            if page_count < fetch_limit:
                break
            
            offset += page_count

    async def first_page(self) -> list[T]:
        """Get just the first page of results."""
        items = []
        limit = self._page_size
        if self._limit is not None:
            limit = min(self._page_size, self._limit)
        
        async for item in self._fetch_func(0, limit):
            items.append(item)
        
        return items

    async def to_list(self) -> list[T]:
        """Convert entire paginator to list."""
        items = []
        async for item in self:
            items.append(item)
        return items


class AsyncBatchIterator(Generic[T]):
    """Async iterator that yields items in batches."""

    def __init__(
        self,
        iterator: AsyncIterator[T],
        batch_size: int = 10,
    ):
        self._iterator = iterator
        self._batch_size = batch_size

    async def __aiter__(self) -> AsyncIterator[list[T]]:
        """Yield batches of items."""
        batch: list[T] = []
        
        async for item in self._iterator:
            batch.append(item)
            if len(batch) >= self._batch_size:
                yield batch
                batch = []
        
        # Yield any remaining items
        if batch:
            yield batch