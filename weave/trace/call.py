import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Optional,
    TypeVar,
    Union,
)

from weave import call_context, client_context
from weave.trace import box
from weave.trace.constants import TRACE_CALL_EMOJI

if TYPE_CHECKING:
    from weave.trace.op import Op
    from weave.weave_client import Call


T = TypeVar("T")


def print_call_link(call: "Call") -> None:
    print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


def create_finish_func(call: "Call", client: Any) -> Callable:
    has_finished = False

    def finish(output: Any = None, exception: Optional[BaseException] = None) -> None:
        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")

        client.finish_call(call, output, exception)
        if not call_context.get_current_call():
            print_call_link(call)

    return finish


def create_on_output_func(__op: Op, finish: Callable, call: "Call") -> Callable:
    def on_output(output: Any) -> Any:
        if handler := getattr(__op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    return on_output


def _execute_call_sync(__op: Op, call: "Call", *args: Any, **kwargs: Any) -> T:
    func = __op.resolve_fn
    client = client_context.weave_client.require_weave_client()

    finish = create_finish_func(call, client)
    on_output = create_on_output_func(__op, finish, call)

    try:
        res = func(*args, **kwargs)
    except Exception as e:
        finish(exception=e)
        raise
    else:
        res = box.box(res)
    return on_output(res)


async def _execute_call_async(
    __op: Op, call: "Call", *args: Any, **kwargs: Any
) -> Coroutine[Any, Any, T]:
    func = __op.resolve_fn
    client = client_context.weave_client.require_weave_client()

    finish = create_finish_func(call, client)
    on_output = create_on_output_func(__op, finish, call)

    try:
        call_context.push_call(call)
        res = await func(*args, **kwargs)
        res = box.box(res)
        return on_output(res)
    except Exception as e:
        finish(exception=e)
        raise
    finally:
        call_context.pop_call(call.id)


def execute_call(
    __op: Op, call: "Call", *args: Any, **kwargs: Any
) -> Union[T, Coroutine[Any, Any, T]]:
    func = __op.resolve_fn
    if inspect.iscoroutinefunction(func):
        return _execute_call_async(__op, call, *args, **kwargs)
    else:
        return _execute_call_sync(__op, call, *args, **kwargs)
