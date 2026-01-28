import pytest

from weave.trace.op import _IteratorWrapper


class _AsyncContextIterator:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False
        self._items = iter([1, 2])

    async def __aenter__(self) -> "_AsyncContextIterator":
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True

    def __aiter__(self) -> "_AsyncContextIterator":
        return self

    async def __anext__(self) -> int:
        try:
            return next(self._items)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.mark.asyncio
async def test_iterator_wrapper_delegates_aexit() -> None:
    stream = _AsyncContextIterator()
    wrapper = _IteratorWrapper(stream, lambda _: None, lambda _: None, lambda: None)

    async with wrapper as wrapped:
        assert stream.entered is True
        values = [value async for value in wrapped]

    assert values == [1, 2]
    assert stream.exited is True
