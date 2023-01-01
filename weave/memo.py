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
            raise errors.WeaveInternalError("no memo storage created")
        f_storage = storage.setdefault(f.__name__, {})
        sig = inspect.signature(f)
        params = sig.bind(*args, **kwargs)
        params_key = tuple(params.arguments.values())
        result = f_storage.get(params_key, NO_VALUE)
        if result is NO_VALUE:
            result = f(*args, **kwargs)
            f_storage[params_key] = result
        return result

    return call_memo
