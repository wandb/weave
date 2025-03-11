"""Defines the Op protocol and related functions."""

from __future__ import annotations

import inspect
import logging
import random
import sys
import traceback
from collections.abc import Callable, Coroutine, Mapping
from dataclasses import dataclass
from functools import partial, wraps
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    ParamSpec,
    Protocol,
    TypedDict,
    TypeGuard,
    TypeVar,
    cast,
    overload,
    runtime_checkable,
)

from weave.trace import box, settings
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.context.call_context import (
    call_attributes,
    get_tracing_enabled,
    tracing_disabled,
)
from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.refs import ObjectRef
from weave.trace.util import log_once

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
    from cerebras.cloud.sdk._types import NOT_GIVEN as CEREBRAS_NOT_GIVEN
except ImportError:
    CEREBRAS_NOT_GIVEN = None

CALL_CREATE_MSG = "Error creating call:\n{}"
ASYNC_CALL_CREATE_MSG = "Error creating async call:\n{}"
ON_OUTPUT_MSG = "Error capturing call output:\n{}"


class DisplayNameFuncError(ValueError): ...


def print_call_link(call: Call) -> None:
    if settings.should_print_call_link():
        print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


@dataclass
class ProcessedInputs:
    # What the user passed to the function
    original_args: tuple
    original_kwargs: dict[str, Any]

    # What should get passed to the interior function
    args: tuple
    kwargs: dict[str, Any]

    # What should get sent to the Weave server
    inputs: dict[str, Any]


OnInputHandlerType = Callable[["Op", tuple, dict], Optional[ProcessedInputs]]
FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, dict], Any]
# Call, original function output, exception if occurred
OnFinishHandlerType = Callable[["Call", Any, Optional[BaseException]], None]


def _value_is_sentinel(param: Any) -> bool:
    return param.default in (
        None,
        Ellipsis,
        OPENAI_NOT_GIVEN,
        COHERE_NOT_GIVEN,
        ANTHROPIC_NOT_GIVEN,
        CEREBRAS_NOT_GIVEN,
    )


def _apply_fn_defaults_to_inputs(
    fn: Callable, inputs: Mapping[str, Any]
) -> dict[str, Any]:
    inputs = {**inputs}
    sig = inspect.signature(fn)
    for name, param in sig.parameters.items():
        if name in inputs:
            continue
        if param.default != inspect.Parameter.empty and not _value_is_sentinel(param):
            inputs[name] = param.default
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            inputs[name] = ()
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            inputs[name] = {}
    return inputs


class WeaveKwargs(TypedDict):
    display_name: str | None


# Type variables for preserving function signatures
P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T", bound=Callable[..., Any])


@runtime_checkable
class Op(Protocol[P, R]):
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
    - _set_on_output_handler (does this have to be on the op?)
    - _on_output_handler (does this have to be on the op?)
    """

    name: str
    call_display_name: str | Callable[[Call], str]
    ref: ObjectRef | None
    resolve_fn: Callable

    postprocess_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None
    postprocess_output: Callable[..., Any] | None

    call: Callable[..., Any]
    calls: Callable[..., CallsIter]

    _set_on_input_handler: Callable[[OnInputHandlerType], None]
    _on_input_handler: OnInputHandlerType | None

    # not sure if this is the best place for this, but kept for compat
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: OnOutputHandlerType | None

    _set_on_finish_handler: Callable[[OnFinishHandlerType], None]
    _on_finish_handler: OnFinishHandlerType | None

    __call__: Callable[P, R]
    __self__: Any

    # `_tracing_enabled` is a runtime-only flag that can be used to disable
    # call tracing for an op. It is not persisted as a property of the op, but is
    # respected by the current execution context. It is an underscore property
    # because it is not intended to be used by users directly, but rather assists
    # with internal Weave behavior. If we find a need to expose this to users, we
    # should consider a more user-friendly API (perhaps a setter/getter) & whether
    # it disables child ops as well.
    _tracing_enabled: bool

    tracing_sample_rate: float


def _set_on_input_handler(func: Op[P, R], on_input: OnInputHandlerType) -> None:
    """Set the on_input handler for an op."""
    if func._on_input_handler is not None:
        raise ValueError("Cannot set on_input_handler multiple times")
    func._on_input_handler = on_input


def _set_on_output_handler(func: Op[P, R], on_output: OnOutputHandlerType) -> None:
    """Set the on_output handler for an op."""
    if func._on_output_handler is not None:
        raise ValueError("Cannot set on_output_handler multiple times")
    func._on_output_handler = on_output


def _set_on_finish_handler(func: Op[P, R], on_finish: OnFinishHandlerType) -> None:
    """Set the on_finish handler for an op."""
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


class OpCallError(Exception): ...


def _default_on_input_handler(
    func: Op[P, R], args: tuple, kwargs: dict
) -> ProcessedInputs:
    """Default handler for processing inputs to an op."""
    try:
        sig = inspect.signature(func)
    except ValueError:
        # This can happen for built-in functions
        return ProcessedInputs(
            original_args=args,
            original_kwargs=kwargs,
            args=args,
            kwargs=kwargs,
            inputs={},
        )

    try:
        inputs = sig.bind(*args, **kwargs).arguments
    except TypeError as e:
        raise OpCallError(f"Error calling {func.name}: {e}")

    inputs_with_defaults = _apply_fn_defaults_to_inputs(func, inputs)
    return ProcessedInputs(
        original_args=args,
        original_kwargs=kwargs,
        args=args,
        kwargs=kwargs,
        inputs=inputs_with_defaults,
    )


def _create_call(
    func: Op[P, R], *args: Any, __weave: WeaveKwargs | None = None, **kwargs: Any
) -> Call:
    """
    Create a Call object for an op call.

    Args:
        func: The op to call.
        *args: Positional arguments to pass to the op.
        __weave: Optional WeaveKwargs to pass to the op.
        **kwargs: Keyword arguments to pass to the op.

    Returns:
        A Call object.
    """
    client = weave_client_context.require_weave_client()

    pargs = None
    if func._on_input_handler is not None:
        pargs = func._on_input_handler(func, args, kwargs)
    if not pargs:
        pargs = _default_on_input_handler(func, args, kwargs)
    inputs_with_defaults = pargs.inputs

    # This should probably be configurable, but for now we redact the api_key
    if "api_key" in inputs_with_defaults:
        inputs_with_defaults["api_key"] = "REDACTED"

    call_time_display_name = __weave.get("display_name") if __weave else None

    # If/When we do memoization, this would be a good spot

    parent_call = call_context.get_current_call()
    attributes = call_attributes.get()
    from weave.trace.serialization.serialize import dictify

    attributes = dictify(attributes)

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        # Very important for `call_time_display_name` to take precedence over `func.call_display_name`
        display_name=call_time_display_name or func.call_display_name,
        attributes=attributes,
    )


def _execute_op(
    __op: Op[P, R],
    __call: Call,
    *args: Any,
    __should_raise: bool = True,
    **kwargs: Any,
) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
    """
    Execute an op and return the result and the Call object.

    Args:
        __op: The op to call.
        __call: The Call object to use.
        *args: Positional arguments to pass to the op.
        __should_raise: Whether to raise exceptions from the op.
        **kwargs: Keyword arguments to pass to the op.

    Returns:
        A tuple of (result, Call) or a coroutine that returns a tuple of (result, Call).
    """
    func = __op.resolve_fn
    client = weave_client_context.require_weave_client()
    has_finished = False

    def finish(output: Any = None, exception: BaseException | None = None) -> None:
        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")

        client.finish_call(
            __call,
            output,
            exception,
            op=__op,
        )

    def on_output(output: Any) -> Any:
        if handler := getattr(__op, "_on_output_handler", None):
            return handler(output, finish, __call.inputs)
        finish(output)
        return output

    def process(res: Any) -> tuple[Any, Call]:
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
            call_context.pop_call(__call.id)

        return res, __call

    def handle_exception(e: Exception) -> tuple[Any, Call]:
        finish(exception=e)
        if __should_raise:
            raise
        return None, __call

    if inspect.iscoroutinefunction(func):

        async def _call_async() -> tuple[Any, Call]:
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

    return None, __call


def call(
    op: Op[P, R],
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
    """
    Call an op and return the result and the Call object.

    This is a lower-level function that most users won't need to use directly.
    It's useful if you want to get the Call object for an op call.

    Args:
        op: The op to call.
        *args: Positional arguments to pass to the op.
        __weave: Optional WeaveKwargs to pass to the op.
        __should_raise: Whether to raise exceptions from the op.
        **kwargs: Keyword arguments to pass to the op.

    Returns:
        A tuple of (result, Call) or a coroutine that returns a tuple of (result, Call).
    """
    if inspect.iscoroutinefunction(op.resolve_fn):
        return _do_call_async(
            op, *args, __weave=__weave, __should_raise=__should_raise, **kwargs
        )
    return _do_call(op, *args, __weave=__weave, __should_raise=__should_raise, **kwargs)


def _placeholder_call() -> Call:
    # Import here to avoid circular dependency
    from weave.trace.weave_client import Call

    return Call(
        _op_name="",
        trace_id="",
        project_id="",
        parent_id=None,
        inputs={},
    )


def _do_call(
    op: Op[P, R],
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
    """
    Execute an op synchronously and return the result and the Call object.

    Args:
        op: The op to call.
        *args: Positional arguments to pass to the op.
        __weave: Optional WeaveKwargs to pass to the op.
        __should_raise: Whether to raise exceptions from the op.
        **kwargs: Keyword arguments to pass to the op.

    Returns:
        A tuple of (result, Call).
    """
    func = op.resolve_fn
    call = _placeholder_call()

    pargs = None
    if op._on_input_handler is not None:
        pargs = op._on_input_handler(op, args, kwargs)
    if not pargs:
        pargs = _default_on_input_handler(op, args, kwargs)

    # Handle all of the possible cases where we would skip tracing.
    if settings.should_disable_weave():
        res = func(*pargs.args, **pargs.kwargs)
        call.output = res
        return res, call
    if weave_client_context.get_weave_client() is None:
        res = func(*pargs.args, **pargs.kwargs)
        call.output = res
        return res, call
    if not op._tracing_enabled:
        res = func(*pargs.args, **pargs.kwargs)
        call.output = res
        return res, call
    if not get_tracing_enabled():
        res = func(*pargs.args, **pargs.kwargs)
        call.output = res
        return res, call

    current_call = call_context.get_current_call()
    if current_call is None:
        # Root call: decide whether to trace based on sample rate
        if random.random() > op.tracing_sample_rate:
            # Disable tracing for this call and all descendants
            with tracing_disabled():
                res = func(*pargs.args, **pargs.kwargs)
                call.output = res
                return res, call

    # Proceed with tracing. Note that we don't check the sample rate here.
    # Only root calls get sampling applied.
    # If the parent was traced (sampled in), the child will be too.
    try:
        call = _create_call(op, *args, __weave=__weave, **kwargs)
    except OpCallError as e:
        raise e
    except Exception as e:
        if get_raise_on_captured_errors():
            raise
        log_once(
            logger.error,
            CALL_CREATE_MSG.format(traceback.format_exc()),
        )
        res = func(*pargs.args, **pargs.kwargs)
    else:
        execute_result = _execute_op(
            op, call, *pargs.args, __should_raise=__should_raise, **pargs.kwargs
        )
        if inspect.iscoroutine(execute_result):
            raise TypeError(
                "Internal error: Expected `_execute_call` to return a sync result"
            )
        execute_result = cast(tuple[Any, "Call"], execute_result)
        res, call = execute_result
    return res, call


async def _do_call_async(
    op: Op[P, R],
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
    """
    Execute an op asynchronously and return the result and the Call object.

    Args:
        op: The op to call.
        *args: Positional arguments to pass to the op.
        __weave: Optional WeaveKwargs to pass to the op.
        __should_raise: Whether to raise exceptions from the op.
        **kwargs: Keyword arguments to pass to the op.

    Returns:
        A tuple of (result, Call).
    """
    func = op.resolve_fn
    call = _placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if settings.should_disable_weave():
        res = await func(*args, **kwargs)
        call.output = res
        return res, call
    if weave_client_context.get_weave_client() is None:
        res = await func(*args, **kwargs)
        call.output = res
        return res, call
    if not op._tracing_enabled:
        res = await func(*args, **kwargs)
        call.output = res
        return res, call
    if not get_tracing_enabled():
        res = await func(*args, **kwargs)
        call.output = res
        return res, call

    current_call = call_context.get_current_call()
    if current_call is None:
        # Root call: decide whether to trace based on sample rate
        if random.random() > op.tracing_sample_rate:
            # Disable tracing for this call and all descendants
            with tracing_disabled():
                res = await func(*args, **kwargs)
                call.output = res
                return res, call

    # Proceed with tracing
    try:
        call = _create_call(op, *args, __weave=__weave, **kwargs)
    except OpCallError as e:
        raise e
    except Exception as e:
        if get_raise_on_captured_errors():
            raise
        log_once(
            logger.error,
            ASYNC_CALL_CREATE_MSG.format(traceback.format_exc()),
        )
        res = await func(*args, **kwargs)
    else:
        execute_result = _execute_op(
            op, call, *args, __should_raise=__should_raise, **kwargs
        )
        if not inspect.iscoroutine(execute_result):
            raise TypeError(
                "Internal error: Expected `_execute_call` to return a coroutine"
            )
        res, call = await execute_result
    return res, call


def calls(op: Op[P, R]) -> CallsIter:
    """
    Get an iterator over all calls to an op.

    Example usage:

    ```python
    for call in my_op.calls():
        print(call)
    ```
    """
    client = weave_client_context.require_weave_client()
    return client._op_calls(op)


CallDisplayNameFunc = Callable[["Call"], str]
PostprocessInputsFunc = Callable[[dict[str, Any]], dict[str, Any]]
PostprocessOutputFunc = Callable[..., Any]


# Type alias for the decorated function type
OpCallable = Callable[P, R]
# Type alias for the decorator type
OpDecorator = Callable[[Callable[P, R]], Callable[P, R]]


@overload
def op(
    func: Callable[P, R],
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    tracing_sample_rate: float = 1.0,
) -> Op[P, R]: ...


@overload
def op(
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    tracing_sample_rate: float = 1.0,
) -> Callable[[Callable[P, R]], Op[P, R]]: ...


def op(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    call_display_name: str | Callable[[Call], str] | None = None,
    postprocess_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    postprocess_output: Callable[..., Any] | None = None,
    tracing_sample_rate: float = 1.0,
) -> Callable[[Callable[P, R]], Op[P, R]] | Op[P, R]:
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
        tracing_sample_rate (float): The sampling rate for tracing this function. Defaults to 1.0 (always trace).

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
    if not isinstance(tracing_sample_rate, (int, float)):
        raise TypeError("tracing_sample_rate must be a float")
    if not 0 <= tracing_sample_rate <= 1:
        raise ValueError("tracing_sample_rate must be between 0 and 1")

    def op_deco(func: Callable[P, R]) -> Op[P, R]:
        # Check function type
        is_method = _is_unbound_method(func)
        is_async = inspect.iscoroutinefunction(func)

        def create_wrapper(func: Callable[P, R]) -> Op[P, R]:
            if is_async:

                @wraps(func)
                async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportRedeclaration]
                    res, _ = await _do_call_async(
                        cast(Op[P, R], wrapper), *args, __should_raise=True, **kwargs
                    )
                    return cast(R, res)
            else:

                @wraps(func)
                def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    res, _ = _do_call(
                        cast(Op[P, R], wrapper), *args, __should_raise=True, **kwargs
                    )
                    return cast(R, res)

            # Tack these helpers on to our wrapper
            wrapper.resolve_fn = func  # type: ignore

            inferred_name = func.__qualname__ if is_method else func.__name__

            # funcs and methods defined inside another func will have the
            # name prefixed with {outer}.<locals>.{func_name}
            # this is noisy for us, so we strip it out
            inferred_name = inferred_name.split(".<locals>.")[-1]

            wrapper.name = name or inferred_name  # type: ignore
            wrapper.ref = None  # type: ignore

            wrapper.postprocess_inputs = postprocess_inputs  # type: ignore
            wrapper.postprocess_output = postprocess_output  # type: ignore

            wrapper.call = partial(call, wrapper)  # type: ignore
            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__call__ = wrapper  # type: ignore
            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_input_handler = partial(_set_on_input_handler, wrapper)  # type: ignore
            wrapper._on_input_handler = None  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore
            wrapper._on_output_handler = None  # type: ignore

            wrapper._set_on_finish_handler = partial(_set_on_finish_handler, wrapper)  # type: ignore
            wrapper._on_finish_handler = None  # type: ignore

            wrapper._tracing_enabled = True  # type: ignore
            wrapper.tracing_sample_rate = tracing_sample_rate  # type: ignore

            wrapper.get_captured_code = partial(get_captured_code, wrapper)  # type: ignore

            if callable(call_display_name):
                params = inspect.signature(call_display_name).parameters
                if len(params) != 1:
                    raise DisplayNameFuncError(
                        "`call_display_name` function must take exactly 1 argument (the Call object)"
                    )
            wrapper.call_display_name = call_display_name  # type: ignore

            return cast(Op[P, R], wrapper)

        return create_wrapper(func)

    if func is None:
        return cast(Callable[[Callable[P, R]], Op[P, R]], op_deco)
    return op_deco(func)


def get_captured_code(op: Op[P, R]) -> str:
    """Get the source code of an op."""
    try:
        return inspect.getsource(op.resolve_fn)
    except (TypeError, OSError):
        return ""


def maybe_bind_method(func: Callable, self: Any = None) -> Callable | MethodType:
    """
    Bind a function to an object if it's an unbound method.

    Args:
        func: The function to bind.
        self: The object to bind the function to.

    Returns:
        The bound method or the original function.
    """
    if (sig := inspect.signature(func)) and sig.parameters.get("self"):
        if inspect.ismethod(func) and id(func.__self__) != id(self):
            raise ValueError("Cannot re-bind a method to an new object")
        return MethodType(func, self)
    return func


def maybe_unbind_method(oplike: Op[P, R] | MethodType | partial) -> Op[P, R]:
    """
    Unbind a method from its object if it's a bound method.

    Args:
        oplike: The method to unbind.

    Returns:
        The unbound method or the original function.
    """
    if isinstance(oplike, MethodType):
        # For methods, we need to get the underlying function
        op = oplike.__func__
    elif isinstance(oplike, partial):
        # For partials, we need to get the underlying function
        op = oplike.func
    else:
        op = oplike

    return cast(Op[P, R], op)


def is_op(obj: Any) -> TypeGuard[Op]:
    """
    Check if an object is an op.

    Args:
        obj: The object to check.

    Returns:
        True if the object is an op, False otherwise.
    """
    if sys.version_info < (3, 12):
        return isinstance(obj, Op)
    else:
        # In Python 3.12, isinstance(obj, Protocol) is not supported
        # See https://peps.python.org/pep-0544/#using-protocols
        return hasattr(obj, "resolve_fn") and callable(obj)


def as_op(fn: Callable[P, R]) -> Op[P, R]:
    """
    Convert a function to an op if it's not already one.

    Args:
        fn: The function to convert.

    Returns:
        The function as an op.
    """
    if is_op(fn):
        return cast(Op[P, R], fn)
    return op(fn)


__docspec__ = [call, calls]
