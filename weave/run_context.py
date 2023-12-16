import contextlib
import contextvars
import typing

if typing.TYPE_CHECKING:
    from .run import Run

_current_run: contextvars.ContextVar[typing.Optional["Run"]] = contextvars.ContextVar(
    "run", default=None
)


@contextlib.contextmanager
def set_current_run(
    client: typing.Optional["Run"],
) -> typing.Iterator[typing.Optional["Run"]]:
    client_token = _current_run.set(client)
    try:
        yield client
    finally:
        _current_run.reset(client_token)


def get_current_run() -> typing.Optional["Run"]:
    return _current_run.get()
