import contextlib
import contextvars
import copy
import logging
import typing

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


def get_current_call() -> typing.Optional["Call"]:
    """Get the Call object for the currently executing Op, within that Op.

    This allows you to access attributes of the Call such as its id or feedback
    while it is running.

    ```python
    @weave.op
    def hello(name: str) -> None:
        print(f"Hello {name}!")
        current_call = weave.get_current_call()
        print(current_call.id)
    ```

    It is also possible to access a Call after the Op has returned.

    If you have the Call's id, perhaps from the UI, you can use the `call` method on the
    `WeaveClient` returned from `weave.init` to retrieve the Call object.

    ```python
    client = weave.init("<project>")
    mycall = client.call("<call_id>")
    ```

    Alternately, after defining your Op you can use its `call` method. For example:

    ```python
    @weave.op
    def hello(name: str) -> None:
        print(f"Hello {name}!")

    mycall = hello.call("world")
    print(mycall.id)
    ```

    Returns:
        The Call object for the currently executing Op, or
        None if tracking has not been initialized or this method is
        invoked outside an Op.
    """
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
