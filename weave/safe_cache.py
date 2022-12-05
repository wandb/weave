import typing
from . import context_state
import functools

F = typing.TypeVar("F", bound=typing.Callable)


def safe_lru_cache(maxsize: int) -> typing.Callable[[F], F]:
    """A namespaced LRU cache."""

    def decorator(f: F) -> F:
        @functools.lru_cache(maxsize)
        def safe_memo_wrap(
            cache_token: str, *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            return f(*args, **kwargs)

        def wrapped(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:

            cache_token = context_state._cache_namespace_token.get()
            return safe_memo_wrap(cache_token, *args, **kwargs)

        return wrapped  # type: ignore

    return decorator
