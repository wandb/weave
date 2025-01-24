from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable, Protocol, Sequence
from typing import Iterator, TypeVar, Union, runtime_checkable

import weave

RawRowsLike = Iterable[dict]
AsyncRawRowsLike = AsyncIterable[dict]
TableRowsLike = Sequence[dict]

T = TypeVar('T', bound=dict)
class SequenceAsIterable(Iterable[T]):
    def __init__(self, seq: Sequence[T]) -> None:
        self.seq = seq

    def __iter__(self) -> Iterator[dict]:
        return iter(self.seq)


class IterableAsSequence(Sequence[T]):
    def __init__(self, iterable: Iterable[T]) -> None:
        self.iterable = iterable
        self.seek = -1
        self.cache = []

    def _seek_to_pos(self, index: int) -> None:
        while self.seek < index:
            try:
                self.cache.append(next(self.iterable))
            except StopIteration:
                raise IndexError(f"index {index} out of bounds for sequence of length {self.seek + 1}")
            self.seek += 1

    def _seek_to_end(self) -> None:
        while True:
            try:
                self.cache.append(next(self.iterable))
            except StopIteration:
                break
            self.seek += 1

    def __getitem__(self, index: int) -> T:
        self._seek_to_pos(index)
        return self.cache[index]

    def __len__(self) -> int:
        self._seek_to_end()
        return len(self.cache)


class SequenceAsAsyncIterable(Iterable[T])
    def __init__(self, seq: Sequence[T]) -> None:
        self.seq = seq

    def __aiter__(self) -> AsyncIterator[T]:
        class AI(AsyncIterator):
            def __init__(self, seq: Sequence[T]) -> None:
                self.seq = seq
                self.index = 0

            async def __anext__(self) -> T:
                if self.index >= len(self.seq):
                    raise StopAsyncIteration
                value = self.seq[self.index]
                self.index += 1
                return value

        return AI(self.seq)


class AsyncIterableAsSequence(Sequence[T]):
    def __init__(self, async_iterable: AsyncIterable[T]) -> None:
        self.async_iterable = async_iterable
        self.seek = -1
        self.cache = []

    def _seek_to_pos(self, index: int) -> None:
        while self.seek < index:
            try:
                self.cache.append(next(self.async_iterable))
            except StopIteration:
                raise IndexError(f"index {index} out of bounds for sequence of length {self.seek + 1}")
            self.seek += 1

    def _seek_to_end(self) -> None:
        while True:
            try:
                self.cache.append(next(self.async_iterable))
            except StopIteration:
                break
            self.seek += 1

    def __getitem__(self, index: int) -> T:
        self._seek_to_pos(index)
        return self.cache[index]

    def __len__(self) -> int:
        self._seek_to_end()
        return len(self.cache)

@runtime_checkable
class TabularProtocol(Protocol):
    def get_rows(self) -> TableRowsLike: ...

    def get_iter(self) -> RawRowsLike: ...

    async def get_async_iter(self) -> AsyncRawRowsLike: ...


class SequenceTableAdapter(TabularProtocol):
    seq: Sequence[dict]

    def get_rows(self) -> TableRowsLike:
        return self.seq

    def get_iter(self) -> RawRowsLike:
        return self.seq

    async def get_async_iter(self) -> AsyncRawRowsLike:

        return self.seq


def _iterable_to_sequence(iterable: RawRowsLike) -> TableRowsLike:
    # TODO: make this lazy
    return list(iterable)

def _async_iterable_to_sequence(iterable: AsyncRawRowsLike) -> TableRowsLike:


class Dataset(weave.Object, TabularProtocol):
    pass

class LocalSequenceTable(TabularProtocol):
    seq: TableRowsLike

    @classmethod
    def from_iterable(cls, iterable: RawRowsLike) -> LocalSequenceTable:
        return cls(seq=_iterable_to_sequence(iterable))

class RemoteTable(TabularProtocol):
    pass

WeaveTable = Union[LocalSequenceTable, RemoteTable]

class WeaveTableDataset(Dataset):
    table: WeaveTable

    def get_rows(self) -> TableRowsLike:
        return self._table.get_rows()

    def get_iter(self) -> RawRowsLike:
        return self._table.get_iter()

    async def get_async_iter(self) -> AsyncRawRowsLike:
        return self._table.get_async_iter()
