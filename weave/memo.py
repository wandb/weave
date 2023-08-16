import typing
import datetime

import contextvars
import contextlib

from . import engine_trace
from . import cache

statsd = engine_trace.statsd()  # type: ignore

_memo_storage: contextvars.ContextVar[typing.Optional[dict]] = contextvars.ContextVar(
    "memo_storage", default=None
)


@contextlib.contextmanager
def memo_storage() -> typing.Generator[None, None, None]:
    # Here we only construct a new context if one does not already exist.
    # This is because we often have recursive calls to the executor (particularly
    # in the case of refinement during querying). In such cases we do not want
    # to reset the memoization storage, as this would cause us to lose the
    # memoized values from the previous call! We might want to do something
    # similar for other context variables.
    token = None
    if _memo_storage.get() is None:
        token = _memo_storage.set({})
    try:
        yield
    finally:
        if token is not None:
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
            val = storage[key]
            # statsd.increment("weave.memo.hit")
            return val
        except KeyError:
            pass
        # statsd.increment("weave.memo.miss")
        result = f(*args, **kwargs)
        storage[key] = result
        return result

    return call_memo


cross_request_cache: cache.LruTimeWindowCache = cache.LruTimeWindowCache(
    datetime.timedelta(seconds=5)
)


def cross_request_memo(f: typing.Any) -> typing.Any:
    def call_memo(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        key = (f, args, tuple(kwargs.items()))
        val = cross_request_cache.get(key)
        if not isinstance(val, cache.LruTimeWindowCache.NotFound):
            # statsd.increment("weave.memo.hit")
            return val
        # statsd.increment("weave.memo.miss")
        result = f(*args, **kwargs)
        cross_request_cache.set(key, result)
        return result

    return call_memo
