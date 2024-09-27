import contextlib
import contextvars
import typing

# Throw an error if op saving encounters an unknonwn condition.
# The default behavior is to warn.
_strict_op_saving: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_strict_op_saving", default=False
)


def get_strict_op_saving() -> bool:
    return _strict_op_saving.get()


@contextlib.contextmanager
def strict_op_saving(enabled: bool) -> typing.Generator[bool, None, None]:
    token = _strict_op_saving.set(enabled)
    yield _strict_op_saving.get()
    _strict_op_saving.reset(token)
