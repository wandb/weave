import contextlib
import contextvars
import typing


_error_on_non_vectorized_history_transform: contextvars.ContextVar[
    bool
] = contextvars.ContextVar("_error_on_non_vectorized_history_transform", default=False)


@contextlib.contextmanager
def error_on_non_vectorized_history_transform(
    should_error: bool = True,
) -> typing.Iterator[None]:
    token = _error_on_non_vectorized_history_transform.set(should_error)
    try:
        yield
    finally:
        _error_on_non_vectorized_history_transform.reset(token)


def get_error_on_non_vectorized_history_transform() -> bool:
    return _error_on_non_vectorized_history_transform.get()
