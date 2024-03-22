import contextlib
import contextvars
import typing
import copy

if typing.TYPE_CHECKING:
    # from .run import Run
    from .weave_client import Call

_run_stack: contextvars.ContextVar[list["Call"]] = contextvars.ContextVar(
    "run", default=[]
)


@contextlib.contextmanager
def current_run(
    run: "Call",
) -> typing.Iterator[list["Call"]]:
    new_stack = copy.copy(_run_stack.get())
    new_stack.append(run)

    token = _run_stack.set(new_stack)
    try:
        yield new_stack
    finally:
        _run_stack.reset(token)


def get_current_run() -> typing.Optional["Call"]:
    return _run_stack.get()[-1] if _run_stack.get() else None


def get_run_stack() -> list["Call"]:
    return _run_stack.get()


@contextlib.contextmanager
def set_run_stack(
    stack: list["Call"],
) -> typing.Iterator[list["Call"]]:
    token = _run_stack.set(stack)
    try:
        yield stack
    finally:
        _run_stack.reset(token)
