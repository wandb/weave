import inspect
import typing
from functools import partial, wraps
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Mapping,
    Optional,
    Protocol,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from weave.legacy.weave import context_state
from weave.trace import box, call_context, settings
from weave.trace.client_context import weave_client as weave_client_context
from weave.trace.context import call_attributes
from weave.trace.errors import OpCallError
from weave.trace.refs import ObjectRef

from .constants import TRACE_CALL_EMOJI

if TYPE_CHECKING:
    from weave.trace.weave_client import Call, CallsIter

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

try:
    from cerebras.cloud.sdk._types import NOT_GIVEN as CEREBRAS_NOT_GIVEN
except ImportError:
    CEREBRAS_NOT_GIVEN = None


def print_call_link(call: "Call") -> None:
    if settings.should_print_call_link():
        print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, Dict], Any]


def value_is_sentinel(param: Any) -> bool:
    return (
        param.default is None
        or param.default is OPENAI_NOT_GIVEN
        or param.default is COHERE_NOT_GIVEN
        or param.default is ANTHROPIC_NOT_GIVEN
        or param.default is CEREBRAS_NOT_GIVEN
    )


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
class Op(Protocol):
    """
    The interface for Op-ified functions and methods.

    Op was previously a class, and has been converted to a Protocol to allow
    functions to pass for Op.  This is needed because many popular packages are
    using the `inspect` module for control flow, and Op instances don't always
    pass those checks.  In particular, `inspect.iscoroutinefunction` always
    fails for classes, even ones that implement async methods or protocols.

    Some of the attributes are carry-overs from when Op was a class.  We should
    consider removing the unnecessary ones where possible.
    - resolve_fn (I think you can just use the func itself?)
    - signature (just inspect the func)
    - _set_on_output_handler (does this have to be on the op?)
    - _on_output_handler (does this have to be on the op?)
    """

    name: str
    signature: inspect.Signature
    ref: Optional[ObjectRef]
    resolve_fn: Callable

    call: Callable[..., Any]
    calls: Callable[..., "CallsIter"]

    # not sure if this is the best place for this, but kept for compat
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: Optional[OnOutputHandlerType]

    __call__: Callable[..., Any]
    __self__: Any

    # `_tracing_enabled` is a runtime-only flag that can be used to disable
    # call tracing for an op. It is not persisted as a property of the op, but is
    # respected by the current execution context. It is an underscore property
    # because it is not intended to be used by users directly, but rather assists
    # with internal Weave behavior. If we find a need to expose this to users, we
    # should consider a more user-friendly API (perhaps a setter/getter) & whether
    # it disables child ops as well.
    _tracing_enabled: bool


def _set_on_output_handler(func: Op, on_output: OnOutputHandlerType) -> None:
    if func._on_output_handler is not None:
        raise ValueError("Cannot set on_output_handler multiple times")
    func._on_output_handler = on_output


def _is_unbound_method(func: Callable) -> bool:
    """Check if a function is a function defined on a class (an "unbound" method)

    In python3, the "unbound" method is just a function, but that distinction is
    not enough for our decorator because it needs to operate on both regular funcs
    and unbound methods at the same time.

    This check clarifies that distinction between function vs. unbound method.
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    is_method = params and params[0].name in {"self", "cls"}

    return bool(is_method)


def _create_call(func: Op, *args: Any, **kwargs: Any) -> "Call":
    client = weave_client_context.require_weave_client()

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
    attributes = call_attributes.get()

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        attributes=attributes,
    )


def _execute_call(
    __op: Op,
    call: Any,
    *args: Any,
    __should_raise: bool = True,
    **kwargs: Any,
) -> Any:
    func = __op.resolve_fn
    client = weave_client_context.require_weave_client()
    has_finished = False

    def finish(output: Any = None, exception: Optional[BaseException] = None) -> None:
        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")

        client.finish_call(call, output, exception)
        if not call_context.get_current_call():
            print_call_link(call)

    def on_output(output: Any) -> Any:
        if handler := getattr(__op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    def process(res: Any) -> Any:
        res = box.box(res)
        res = on_output(res)
        return res, call

    def handle_exception(e: Exception) -> Any:
        finish(exception=e)
        if __should_raise:
            raise
        return None, call

    if inspect.iscoroutinefunction(func):

        async def _call_async() -> Coroutine[Any, Any, Any]:
            call_context.push_call(call)
            try:
                res = await func(*args, **kwargs)
            except Exception as e:
                return handle_exception(e)
            else:
                return process(res)
            finally:
                call_context.pop_call(call.id)

        return _call_async()

    try:
        res = func(*args, **kwargs)
    except Exception as e:
        handle_exception(e)
    else:
        return process(res)

    return None, call


def call(op: Op, *args: Any, **kwargs: Any) -> tuple[Any, "Call"]:
    """
    Executes the op and returns both the result and a Call representing the execution.

    This function will never raise.  Any errors are captured in the Call object.
    """
    c = _create_call(op, *args, **kwargs)
    return _execute_call(op, c, *args, __should_raise=False, **kwargs)


def calls(op: Op) -> "CallsIter":
    client = weave_client_context.require_weave_client()
    return client._op_calls(op)


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
@overload
def op(
    input_type: Any = None,
    output_type: Any = None,
    refine_output_type: Any = None,
    name: Any = None,
    setter: Any = None,
    render_info: Any = None,
    hidden: Any = None,
    pure: Any = None,
    _op_def_class: Any = None,
    plugins: Any = None,
    mutation: Any = None,
    weavify: Any = None,
) -> Any: ...


# Modern decos
@overload
def op(func: Any) -> Op: ...


def op(*args: Any, **kwargs: Any) -> Union[Callable[[Any], Op], Op]:
    """
    A decorator to weave op-ify a function or method.  Works for both sync and async.

    Decorated functions and methods can be called as normal, but will also
    automatically track calls in the Weave UI.

    If you don't call `weave.init` then the function will behave as if it were
    not decorated.


    Example usage:

    ```python
    import weave
    weave.init("my-project")

    @weave.op
    async def extract():
        return await client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": "Create a user as JSON"},
            ],
        )

    await extract()  # calls the function and tracks the call in the Weave UI
    ```
    """
    if context_state.get_loading_built_ins():
        from weave.legacy.weave.decorator_op import op as legacy_op

        return legacy_op(*args, **kwargs)  # type: ignore

    def op_deco(func: Callable) -> Op:
        # Check function type
        sig = inspect.signature(func)
        is_method = _is_unbound_method(func)
        is_async = inspect.iscoroutinefunction(func)

        def create_wrapper(func: Callable) -> Op:
            if is_async:

                @wraps(func)
                async def wrapper(*args: Any, **kwargs: Any) -> Any:
                    if settings.should_disable_weave():
                        return await func(*args, **kwargs)
                    if weave_client_context.get_weave_client() is None:
                        return await func(*args, **kwargs)
                    if not wrapper._tracing_enabled:  # type: ignore
                        return await func(*args, **kwargs)
                    call = _create_call(wrapper, *args, **kwargs)  # type: ignore
                    res, _ = await _execute_call(wrapper, call, *args, **kwargs)  # type: ignore
                    return res
            else:

                @wraps(func)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    if settings.should_disable_weave():
                        return func(*args, **kwargs)
                    if weave_client_context.get_weave_client() is None:
                        return func(*args, **kwargs)
                    if not wrapper._tracing_enabled:  # type: ignore
                        return func(*args, **kwargs)
                    call = _create_call(wrapper, *args, **kwargs)  # type: ignore
                    res, _ = _execute_call(wrapper, call, *args, **kwargs)  # type: ignore
                    return res

            # Tack these helpers on to our wrapper
            wrapper.resolve_fn = func  # type: ignore

            name = func.__qualname__ if is_method else func.__name__

            # funcs and methods defined inside another func will have the
            # name prefixed with {outer}.<locals>.{func_name}
            # this is noisy for us, so we strip it out
            name = name.split(".<locals>.")[-1]

            wrapper.name = name  # type: ignore
            wrapper.signature = sig  # type: ignore
            wrapper.ref = None  # type: ignore

            wrapper.call = partial(call, wrapper)  # type: ignore
            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__call__ = wrapper  # type: ignore
            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore
            wrapper._on_output_handler = None  # type: ignore

            wrapper._tracing_enabled = True  # type: ignore

            return cast(Op, wrapper)

        return create_wrapper(func)

    if len(args) == 1 and len(kwargs) == 0 and callable(func := args[0]):
        # return wrap(args[0])
        return op_deco(func)

    return op_deco


def maybe_bind_method(func: Callable, self: Any = None) -> Union[Callable, MethodType]:
    """Bind a function to any object (even if it's not a class)

    If self is None, return the function as is.
    """
    if (sig := inspect.signature(func)) and sig.parameters.get("self"):
        if inspect.ismethod(func) and id(func.__self__) != id(self):
            raise ValueError("Cannot re-bind a method to an new object")
        return MethodType(func, self)
    return func


def maybe_unbind_method(oplike: Union[Op, MethodType, partial]) -> Op:
    """Unbind an Op-like method or partial to a plain Op function.

    For:
    - methods, remove set `self` param
    - partials, remove any preset params
    """
    if isinstance(oplike, MethodType):
        op = oplike.__func__
    elif isinstance(oplike, partial):  # Handle cases op is defined as
        op = oplike.func
    else:
        op = oplike

    return cast(Op, op)
