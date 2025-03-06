from __future__ import annotations

from collections.abc import Generator, Iterator, Sequence
from threading import Lock
from typing import Any, TypeVar, overload

T = TypeVar("T")


class ThreadSafeLazyList(Sequence[T]):
    """
    Provides a thread-safe, iterable sequence by caching results in memory.

    This class is thread-safe and supports multiple iterations over the same data and
    concurrent access.

    Args:
        single_use_iterator: The source iterator whose values will be cached. (must terminate!)
        known_length: Optional pre-known length of the iterator. If provided, can improve
            performance by avoiding the need to exhaust the iterator to determine length.

    Thread Safety:
        All operations are thread-safe through the use of internal locking.
    """

    _single_use_iterator: Iterator[T]

    def __init__(
        self, single_use_iterator: Iterator[T], known_length: int | None = None
    ) -> None:
        self._lock = Lock()
        self._single_use_iterator = single_use_iterator
        self._list: list[T] = []
        self._stop_reached = False
        self._known_length = known_length

    def _seek_to_index(self, index: int) -> None:
        """
        Advances the iterator until the specified index is reached or iterator is exhausted.
        Thread-safe operation.
        """
        with self._lock:
            while index >= len(self._list):
                try:
                    self._list.append(next(self._single_use_iterator))
                except StopIteration:
                    self._stop_reached = True
                    return

    def _seek_to_end(self) -> None:
        """
        Exhausts the iterator, caching all remaining values.
        Thread-safe operation.
        """
        with self._lock:
            while not self._stop_reached:
                try:
                    self._list.append(next(self._single_use_iterator))
                except StopIteration:
                    self._stop_reached = True
                    return

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[T]: ...

    def __getitem__(self, index: int | slice) -> T | Sequence[T]:
        """
        Returns the item at the specified index.

        Args:
            index: The index of the desired item.

        Returns:
            The item at the specified index.

        Raises:
            IndexError: If the index is out of range.
        """
        if isinstance(index, slice):
            if index.stop is None:
                self._seek_to_end()
            else:
                self._seek_to_index(index.stop)
            return self._list[index]
        else:
            self._seek_to_index(index)
            return self._list[index]

    def __len__(self) -> int:
        """
        Returns the total length of the sequence.

        If known_length was provided at initialization, returns that value.
        Otherwise, exhausts the iterator to determine the length.

        Returns:
            The total number of items in the sequence.
        """
        if self._known_length is not None:
            return self._known_length

        self._seek_to_end()
        return len(self._list)

    def __iter__(self) -> Iterator[T]:
        """
        Returns an iterator over the sequence.

        The returned iterator is safe to use concurrently with other operations
        on this sequence.

        Returns:
            An iterator yielding all items in the sequence.
        """

        def _iter() -> Generator[T, None, None]:
            i = 0
            while True:
                try:
                    val = self[i]
                except IndexError:
                    return
                try:
                    yield val
                finally:
                    i += 1

        return _iter()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Sequence):
            return False
        if len(self) != len(other):
            return False
        self._seek_to_end()
        for a, b in zip(self._list, other):
            if a != b:
                return False
        return True
