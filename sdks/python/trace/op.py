"""Defines the Op protocol and related functions."""

import inspect
import logging
import sys
import traceback
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

from weave.trace import box, call_context, settings
from weave.trace.client_context import weave_client as weave_client_context
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.context import call_attributes, get_raise_on_captured_errors
from weave.trace.errors import OpCallError
from weave.trace.op_extensions.log_once import log_once
from weave.trace.refs import ObjectRef

logger = logging.getLogger(__name__)


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
    # https://github.com/search?q=repo:mistralai/client-python%20Final&type=code
    from mistralai.types.basemodel import UNSET  # type: ignore

    MISTRAL_NOT_GIVEN = UNSET  # type: ignore
except ImportError:
    MISTRAL_NOT_GIVEN = None

MISTRAL_NOT_GIVEN = None


try:
    from cerebras.cloud.sdk._types import NOT_GIVEN as CEREBRAS_NOT_GIVEN
except ImportError:
    CEREBRAS_NOT_GIVEN = None

CALL_CREATE_MSG = "Error creating call:\n{}"
ASYNC_CALL_CREATE_MSG = "Error creating async call:\n{}"
ON_OUTPUT_MSG = "Error capturing call output:\n{}"


class DisplayNameFuncError(ValueError): ...


def print_call_link(call: "Call") -> None:
    if settings.should_print_call_link():
        print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, Dict], Any]
# Call, original function output, exception if occurred
OnFinishHandlerType = Callable[["Call", Any, Optional[BaseException]], None]


def value_is_sentinel(param: Any) -> bool:
    return (
        param.default is None
        or param.default is OPENAI_NOT_GIVEN
        or param.default is COHERE_NOT_GIVEN
        or param.default is ANTHROPIC_NOT_GIVEN
        or param.default is MISTRAL_NOT_GIVEN
        or param.default is CEREBRAS_NOT_GIVEN
        or param.default is Ellipsis
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
    call_display_name: Union[str, Callable[["Call"], str]]
    signature: inspect.Signature
    ref: Optional[ObjectRef]
    resolve_fn: Callable

    postprocess_inputs: Optional[Callable[[dict[str, Any]], dict[str, Any]]]
    postprocess_output: Optional[Callable[..., Any]]

    call: Callable[..., Any]
    calls: Callable[..., "CallsIter"]

    # not sure if this is the best place for this, but kept for compat
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: Optional[OnOutputHandlerType]

    _set_on_finish_handler: Callable[[OnFinishHandlerType], None]
    _on_finish_handler: Optional[OnFinishHandlerType]

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


def _set_on_finish_handler(func: Op, on_finish: OnFinishHandlerType) -> None:
    if func._on_finish_handler is not None:
        raise ValueError("Cannot set on_finish_handler multiple times")
    func._on_finish_handler = on_finish


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
        display_name=func.call_display_name,
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

        client.finish_call(
            call,
            output,
            exception,
            op=__op,
        )
        if not call_context.get_current_call():
            print_call_link(call)

    def on_output(output: Any) -> Any:
        if handler := getattr(__op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    def process(res: Any) -> Any:
        res = box.box(res)
        try:
            # Here we do a try/catch because we don't want to
            # break the user process if we trip up on processing
            # the output
            res = on_output(res)
        except Exception as e:
            if get_raise_on_captured_errors():
                raise
            log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))
        finally:
            # Is there a better place for this? We want to ensure that even
            # if the final output fails to be captured, we still pop the call
            # so we don't put future calls under the old call.
            call_context.pop_call(call.id)

        return res, call

    def handle_exception(e: Exception) -> Any:
        finish(exception=e)
        if __should_raise:
            raise
        return None, call

    if inspect.iscoroutinefunction(func):

        async def _call_async() -> Coroutine[Any, Any, Any]:
            try:
                res = await func(*args, **kwargs)
            except Exception as e:
                return handle_exception(e)
            else:
                return process(res)

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

    This method is automatically bound to any function decorated with `@weave.op`,
    allowing for usage like:

    ```python
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    result, call = add.call(1, 2)
    ```
    """
    c = _create_call(op, *args, **kwargs)
    return _execute_call(op, c, *args, __should_raise=False, **kwargs)


def calls(op: Op) -> "CallsIter":
    """
    Get an iterator over all calls to this op.

    This method is automatically bound to any function decorated with `@weave.op`,
    allowing for usage like:

    ```python
    @weave.op
    def add(a: int, b: int) -> int:
        return a + b

    calls = add.calls()
    for call in calls:
        print(call)
    ```
    """
    client = weave_client_context.require_weave_client()
    return client._op_calls(op)


CallDisplayNameFunc = Callable[["Call"], str]
PostprocessInputsFunc = Callable[[dict[str, Any]], dict[str, Any]]
PostprocessOutputFunc = Callable[..., Any]


@overload
def op(
    func: Callable,
    *,
    name: Optional[str] = None,
    call_display_name: Optional[Union[str, CallDisplayNameFunc]] = None,
    postprocess_inputs: Optional[PostprocessInputsFunc] = None,
    postprocess_output: Optional[PostprocessOutputFunc] = None,
) -> Op: ...


@overload
def op(
    *,
    name: Optional[str] = None,
    call_display_name: Optional[Union[str, CallDisplayNameFunc]] = None,
    postprocess_inputs: Optional[PostprocessInputsFunc] = None,
    postprocess_output: Optional[PostprocessOutputFunc] = None,
) -> Callable[[Callable], Op]: ...


def op(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    call_display_name: Optional[Union[str, CallDisplayNameFunc]] = None,
    postprocess_inputs: Optional[PostprocessInputsFunc] = None,
    postprocess_output: Optional[PostprocessOutputFunc] = None,
) -> Union[Callable[[Any], Op], Op]:
    """
    A decorator to weave op-ify a function or method.  Works for both sync and async.

    Decorated functions and methods can be called as normal, but will also
    automatically track calls in the Weave UI.

    If you don't call `weave.init` then the function will behave as if it were
    not decorated.


    Args:
        func (Optional[Callable]): The function to be decorated. If None, the decorator
            is being called with parameters.
        name (Optional[str]): Custom name for the op. If None, the function's name is used.
        call_display_name (Optional[Union[str, Callable[["Call"], str]]]): Custom display name
            for the call in the Weave UI. Can be a string or a function that takes a Call
            object and returns a string.  When a function is passed, it can use any attributes
            of the Call object (e.g. `op_name`, `trace_id`, etc.) to generate a custom display name.
        postprocess_inputs (Optional[Callable[[dict[str, Any]], dict[str, Any]]]): A function
            to process the inputs after they've been captured but before they're logged.  This
            does not affect the actual inputs passed to the function, only the displayed inputs.
        postprocess_output (Optional[Callable[..., Any]]): A function to process the output
            after it's been returned from the function but before it's logged.  This does not
            affect the actual output of the function, only the displayed output.

    Returns:
        Union[Callable[[Any], Op], Op]: If called without arguments, returns a decorator.
        If called with a function, returns the decorated function as an Op.

    Raises:
        ValueError: If the decorated object is not a function or method.


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
                    try:
                        # This try/except allows us to fail gracefully and
                        # still let the user code continue to execute
                        call = _create_call(wrapper, *args, **kwargs)  # type: ignore
                    except Exception as e:
                        if get_raise_on_captured_errors():
                            raise
                        log_once(
                            logger.error,
                            ASYNC_CALL_CREATE_MSG.format(traceback.format_exc()),
                        )
                        return await func(*args, **kwargs)
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
                    try:
                        # This try/except allows us to fail gracefully and
                        # still let the user code continue to execute
                        call = _create_call(wrapper, *args, **kwargs)  # type: ignore
                    except Exception as e:
                        if get_raise_on_captured_errors():
                            raise
                        log_once(
                            logger.error, CALL_CREATE_MSG.format(traceback.format_exc())
                        )
                        return func(*args, **kwargs)
                    res, _ = _execute_call(wrapper, call, *args, **kwargs)  # type: ignore
                    return res

            # Tack these helpers on to our wrapper
            wrapper.resolve_fn = func  # type: ignore

            inferred_name = func.__qualname__ if is_method else func.__name__

            # funcs and methods defined inside another func will have the
            # name prefixed with {outer}.<locals>.{func_name}
            # this is noisy for us, so we strip it out
            inferred_name = inferred_name.split(".<locals>.")[-1]

            wrapper.name = name or inferred_name  # type: ignore
            wrapper.signature = sig  # type: ignore
            wrapper.ref = None  # type: ignore

            wrapper.postprocess_inputs = postprocess_inputs  # type: ignore
            wrapper.postprocess_output = postprocess_output  # type: ignore

            wrapper.call = partial(call, wrapper)  # type: ignore
            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__call__ = wrapper  # type: ignore
            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore
            wrapper._on_output_handler = None  # type: ignore

            wrapper._set_on_finish_handler = partial(_set_on_finish_handler, wrapper)  # type: ignore
            wrapper._on_finish_handler = None  # type: ignore

            wrapper._tracing_enabled = True  # type: ignore

            if callable(call_display_name):
                params = inspect.signature(call_display_name).parameters
                if len(params) != 1:
                    raise DisplayNameFuncError(
                        "`call_display_name` function must take exactly 1 argument (the Call object)"
                    )
            wrapper.call_display_name = call_display_name  # type: ignore

            return cast(Op, wrapper)

        return create_wrapper(func)

    if func is None:
        return op_deco
    return op_deco(func)


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


def is_op(obj: Any) -> bool:
    if sys.version_info < (3, 12):
        return isinstance(obj, Op)

    return all(hasattr(obj, attr) for attr in Op.__annotations__)


def as_op(fn: Callable) -> Op:
    """Given a @weave.op() decorated function, return its Op.

    @weave.op() decorated functions are instances of Op already, so this
    function should be a no-op at runtime. But you can use it to satisfy type checkers
    if you need to access OpDef attributes in a typesafe way.

    Args:
        fn: A weave.op() decorated function.

    Returns:
        The Op of the function.
    """
    if not is_op(fn):
        raise ValueError("fn must be a weave.op() decorated function")

    return cast(Op, fn)


__docspec__ = [call, calls]
