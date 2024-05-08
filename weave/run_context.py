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


def push_call(run: "Call") -> None:
    new_stack = copy.copy(_run_stack.get())
    new_stack.append(run)
    _run_stack.set(new_stack)


def pop_call(run_id: typing.Optional[str]) -> None:
    new_stack = copy.copy(_run_stack.get())
    if run_id:
        id_found = False
        for i, call in enumerate(new_stack):
            if call.id == run_id:
                id_found = True
                break
        if id_found:
            new_stack = new_stack[: i + 1]
        else:
            raise ValueError(f"Run with id {run_id} not found in stack")
    else:
        new_stack.pop()
    _run_stack.set(new_stack)


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
