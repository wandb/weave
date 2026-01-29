import pytest

from weave.integrations.anthropic.anthropic_sdk import AnthropicIteratorWrapper


class _AsyncContextIterator:
    def __init__(self, open_handles: list["_AsyncContextIterator"]) -> None:
        self.entered = False
        self.exited = False
        self._open_handles = open_handles
        self._items = iter([1, 2])

    async def __aenter__(self) -> "_AsyncContextIterator":
        self.entered = True
        self._open_handles.append(self)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True
        self._open_handles.remove(self)

    def __aiter__(self) -> "_AsyncContextIterator":
        return self

    async def __anext__(self) -> int:
        try:
            return next(self._items)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


@pytest.mark.asyncio
async def test_anthropic_iterator_wrapper_delegates_aexit() -> None:
    open_handles: list[_AsyncContextIterator] = []
    stream = _AsyncContextIterator(open_handles)
    wrapper = AnthropicIteratorWrapper(
        stream, lambda _: None, lambda _: None, lambda: None
    )

    async with wrapper as wrapped:
        assert stream.entered is True
        values = [value async for value in wrapped]

    assert values == [1, 2]
    # If this fails, AnthropicIteratorWrapper.__aexit__ is not delegating to the
    # wrapped async context manager, which can leak streaming connections.
    assert stream.exited is True
    assert open_handles == []
