import contextlib
import contextvars
import typing
import copy
import logging

if typing.TYPE_CHECKING:
    # from .run import Run
    from .weave_client import Call

_run_stack: contextvars.ContextVar[list["Call"]] = contextvars.ContextVar(
    "run", default=[]
)

logger = logging.getLogger(__name__)


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


def pop_call(call_id: typing.Optional[str]) -> None:
    new_stack = copy.copy(_run_stack.get())
    if len(new_stack) == 0:
        logger.warning(
            f"weave pop_call error: Found empty callstack when popping call_id: {call_id}."
        )
        # raise ValueError("Call stack is empty")
        return
    if call_id:
        # assert that the call_id is in the stack
        for i in range(len(new_stack)):
            target_index = -(i + 1)
            call = new_stack[target_index]
            if call.id == call_id:
                # Actually do the slice
                new_stack = new_stack[:target_index]
                break
        else:
            logger.warning(
                f"weave pop_call error: Call with id {call_id} not found in stack."
            )
            # raise ValueError(f"Call with id {call_id} not found in stack")
            return
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
