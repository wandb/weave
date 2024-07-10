import inspect
import typing
from functools import partial, wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Literal,
    Mapping,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from weave import call_context, client_context
from weave.legacy import box, context_state
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.context import call_attributes
from weave.trace.errors import OpCallError
from weave.trace.refs import ObjectRef

from .constants import TRACE_CALL_EMOJI

T = TypeVar("T", bound=Callable[..., Any])

if TYPE_CHECKING:
    from weave.weave_client import Call, CallsIter

try:
    from openai._types import NOT_GIVEN as OPENAI_NOT_GIVEN
except ImportError:
    OPENAI_NOT_GIVEN = None


def print_call_link(call: "Call") -> None:
    print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, Dict], Any]


def value_is_sentinel(param: Any) -> bool:
    return param.default is None or param.default is OPENAI_NOT_GIVEN


def _apply_fn_defaults_to_inputs(
    fn: typing.Callable, inputs: Mapping[str, typing.Any]
) -> dict[str, typing.Any]:
    inputs = {**inputs}
    sig = inspect.signature(fn)
    for param_name, param in sig.parameters.items():
        if param_name not in inputs:
            if param.default != inspect.Parameter.empty and not value_is_sentinel(
                param
            ):
                inputs[param_name] = param.default
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                inputs[param_name] = tuple()
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                inputs[param_name] = dict()
    return inputs


@runtime_checkable
class Op2(Protocol):
    name: str
    signature: inspect.Signature
    ref: Optional[ObjectRef]
    resolve_fn: Callable

    call: Callable[..., Any]
    calls: Callable[..., "CallsIter"]

    # this should not be here but kept for simplicity for now
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: Optional[OnOutputHandlerType]

    __call__: Callable[..., Any]
    __self__: Any


def _set_on_output_handler(func: Op2, on_output: OnOutputHandlerType) -> None:
    if func._on_output_handler is not None:
        raise ValueError("Cannot set on_output_handler multiple times")
    func._on_output_handler = on_output


def _is_method_alt(func: Callable) -> bool:
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    is_method = params and params[0].name in {"self", "cls"}

    return bool(is_method)


def _create_call(func: Op2, *args: Any, **kwargs: Any) -> "Call":
    client = client_context.weave_client.require_weave_client()

    try:
        inputs = func.signature.bind(*args, **kwargs).arguments
    except TypeError as e:
        raise OpCallError(f"Error calling {func.name}: {e}")
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


def _execute_call(
    wrapper: Op2,
    call: Any,
    *args: Any,
    return_type: Literal["call", "value"] = "call",
    **kwargs: Any,
) -> Any:
    func = wrapper.resolve_fn
    client = client_context.weave_client.require_weave_client()
    has_finished = False

    def finish(output: Any = None, exception: Optional[BaseException] = None) -> None:
        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")
        client.finish_call(call, output, exception)
        if not call_context.get_current_call():
            print_call_link(call)

    def on_output(output: Any) -> Any:
        if handler := getattr(wrapper, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    try:
        res = func(*args, **kwargs)
    except BaseException as e:
        finish(exception=e)
        raise
    else:
        res = box.box(res)  # TODO: can we get rid of this?
    # We cannot let BoxedNone or BoxedBool escape into the user's code
    # since they cannot pass instance checks for None or bool.
    if isinstance(res, box.BoxedNone):
        res = None
    if isinstance(res, box.BoxedBool):
        res = res.val

    if inspect.iscoroutine(res):
        awaitable = res

        async def _call_async() -> Coroutine[Any, Any, Any]:
            try:
                call_context.push_call(call)
                output = await awaitable
                res2 = on_output(output)
                return call if return_type == "call" else res2
            except BaseException as e:
                finish(exception=e)
                raise
            finally:
                call_context.pop_call(call.id)

        return _call_async()
    else:
        res2 = on_output(res)
        return call if return_type == "call" else res2


def call(func: Op2, *args: Any, **kwargs: Any) -> Any:
    # There is probably a better place for this
    if _is_method_alt(func):
        self = func.__self__
        args = (self,) + args
    c = _create_call(func, *args, **kwargs)
    res = _execute_call(func, c, *args, **kwargs)
    return res


def calls(func: Op2) -> "CallsIter":
    client = client_context.weave_client.require_weave_client()
    return client._op_calls(func)


# Legacy decos
@overload
def op(name: Any) -> Any: ...
@overload
def op(input_type: Any, output_type: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any) -> Any: ...
@overload
def op(name: Any, output_type: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any, render_info: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any, pure: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any, hidden: Any) -> Any: ...


# Modern decos
@overload
def op() -> Callable[[Any], Op2]: ...
@overload
def op(func: Any) -> Op2: ...


def op(*args: Any, **kwargs: Any) -> Union[Callable[[Any], Op2], Op2]:
    """The op decorator!"""
    if context_state.get_loading_built_ins():
        from weave.legacy.decorator_op import op as legacy_op

        return legacy_op(*args, **kwargs)  # type: ignore

    def op_deco(func: Callable) -> Op2:
        # Check function type
        sig = inspect.signature(func)
        is_method = _is_method_alt(func)
        is_async = inspect.iscoroutinefunction(func)

        def create_wrapper(func: Callable) -> Op2:
            if is_async:

                @wraps(func)
                async def wrapper(*args: Any, **kwargs: Any) -> Any:
                    if client_context.weave_client.get_weave_client() is None:
                        return await func(*args, **kwargs)
                    call = _create_call(wrapper, *args, **kwargs)  # type: ignore
                    return await _execute_call(
                        wrapper,  # type: ignore
                        call,
                        *args,
                        return_type="value",
                        **kwargs,
                    )
            else:

                @wraps(func)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    if client_context.weave_client.get_weave_client() is None:
                        return func(*args, **kwargs)
                    call = _create_call(wrapper, *args, **kwargs)  # type: ignore
                    return _execute_call(
                        wrapper,  # type: ignore
                        call,
                        *args,
                        return_type="value",
                        **kwargs,
                    )

            # Tack these helpers on to our wrapper
            wrapper.resolve_fn = func  # type: ignore
            wrapper.name = func.__qualname__ if is_method else func.__name__  # type: ignore
            wrapper.signature = sig  # type: ignore
            wrapper.ref = None  # type: ignore

            wrapper.call = partial(call, wrapper)  # type: ignore
            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__call__ = wrapper  # type: ignore
            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore
            wrapper._on_output_handler = None  # type: ignore

            return cast(Op2, wrapper)

        return create_wrapper(func)

    if len(args) == 1 and len(kwargs) == 0 and callable(func := args[0]):
        # return wrap(args[0])
        return op_deco(func)

    return op_deco
