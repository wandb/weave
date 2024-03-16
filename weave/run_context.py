import contextlib
import contextvars
import typing
import copy

if typing.TYPE_CHECKING:
    from .run import Run

_run_stack: contextvars.ContextVar[list["Run"]] = contextvars.ContextVar(
    "run", default=[]
)


@contextlib.contextmanager
def current_run(
    run: "Run",
) -> typing.Iterator[list["Run"]]:
    new_stack = copy.copy(_run_stack.get())
    new_stack.append(run)

    token = _run_stack.set(new_stack)
    try:
        yield new_stack
    finally:
        _run_stack.reset(token)


def get_current_run() -> typing.Optional["Run"]:
    return _run_stack.get()[-1] if _run_stack.get() else None


def get_run_stack() -> list["Run"]:
    return _run_stack.get()


@contextlib.contextmanager
def set_run_stack(
    stack: list["Run"],
) -> typing.Iterator[list["Run"]]:
    token = _run_stack.set(stack)
    try:
        yield stack
    finally:
        _run_stack.reset(token)
