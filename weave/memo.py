import inspect
import typing

import contextvars
import contextlib

from . import errors

_memo_storage: contextvars.ContextVar[typing.Optional[dict]] = contextvars.ContextVar(
    "memo_storage", default=None
)


@contextlib.contextmanager
def memo_storage() -> typing.Generator[None, None, None]:
    token = _memo_storage.set({})
    try:
        yield
    finally:
        _memo_storage.reset(token)


class NoValue:
    pass


NO_VALUE = NoValue()


def memo(f: typing.Any) -> typing.Any:
    def call_memo(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        storage = _memo_storage.get()
        if storage is None:
            return f(*args, **kwargs)
        key = (f, args, tuple(kwargs.items()))
        try:
            return storage[key]
        except KeyError:
            pass
        result = f(*args, **kwargs)
        storage[key] = result
        return result

    return call_memo
