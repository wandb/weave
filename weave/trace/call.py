import inspect
import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Mapping,
    Optional,
    TypeVar,
)

from weave import call_context, client_context
from weave.trace import box
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.context import call_attributes
from weave.trace.errors import OpCallError

if TYPE_CHECKING:
    from weave.trace.op import Op
    from weave.weave_client import Call


try:
    from openai._types import NOT_GIVEN as OPENAI_NOT_GIVEN
except ImportError:
    OPENAI_NOT_GIVEN = None

try:
    from cohere.base_client import COHERE_NOT_GIVEN
except ImportError:
    COHERE_NOT_GIVEN = None

try:
    from anthropic._types import NOT_GIVEN as ANTHROPIC_NOT_GIVEN
except ImportError:
    ANTHROPIC_NOT_GIVEN = None


T = TypeVar("T")


def _print_call_link(call: "Call") -> None:
    print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


def _value_is_sentinel(param: Any) -> bool:
    return param.default in (
        None,
        OPENAI_NOT_GIVEN,
        COHERE_NOT_GIVEN,
        ANTHROPIC_NOT_GIVEN,
    )


def _apply_fn_defaults_to_inputs(
    fn: Callable, inputs: Mapping[str, Any]
) -> dict[str, Any]:
    inputs = {**inputs}
    sig = inspect.signature(fn)
    for param_name, param in sig.parameters.items():
        if param_name not in inputs:
            if param.default != inspect.Parameter.empty and not _value_is_sentinel(
                param
            ):
                inputs[param_name] = param.default
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                inputs[param_name] = tuple()
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                inputs[param_name] = dict()
    return inputs


def create_finish_func(call: "Call", client: Any) -> Callable:
    has_finished = False

    def finish(output: Any = None, exception: Optional[BaseException] = None) -> None:
        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")

        client.finish_call(call, output, exception)
        if not call_context.get_current_call():
            _print_call_link(call)

    return finish


def create_on_output_func(__op: "Op", finish: Callable, call: "Call") -> Callable:
    def on_output(output: Any) -> Any:
        if handler := getattr(__op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    return on_output


def _execute_call_sync(__op: "Op", call: "Call", *args: Any, **kwargs: Any) -> Any:
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
    __op: "Op", call: "Call", *args: Any, **kwargs: Any
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


def create_call(func: "Op", *args: Any, **kwargs: Any) -> "Call":
    client = client_context.weave_client.require_weave_client()

    try:
        inputs = func.signature.bind(*args, **kwargs).arguments
    except TypeError as e:
        raise OpCallError(f"Failed to bind inputs to {func}: {e}")

    inputs_with_defaults = _apply_fn_defaults_to_inputs(func, inputs)

    # This should probably be configurable, but for now we redact the api_key
    if "api_key" in inputs_with_defaults:
        inputs_with_defaults["api_key"] = "REDACTED"

    # If/When we do memoization, this would be a good spot

    parent_call = call_context.get_current_call()
    client._save_nested_objects(inputs_with_defaults)
    attributes = call_attributes.get()

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        attributes=attributes,
    )


async def _call_async(op: "Op", *args: Any, **kwargs: Any) -> tuple[Any, "Call"]:
    _call = create_call(op, *args, **kwargs)
    try:
        return await _execute_call_async(op, _call, *args, **kwargs), _call
    except Exception:
        print("WARNING: Error executing call")
        traceback.print_exc()
    finally:
        return None, _call


def _call_sync(op: "Op", *args: Any, **kwargs: Any) -> tuple[Any, "Call"]:
    _call = create_call(op, *args, **kwargs)
    try:
        return _execute_call_sync(op, _call, *args, **kwargs), _call
    except Exception:
        print("WARNING: Error executing call")
        traceback.print_exc()
    finally:
        return None, _call
