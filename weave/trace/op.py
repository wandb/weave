"""Defines the Op protocol and related functions."""

from __future__ import annotations

import atexit
import inspect
import logging
import random
import sys
import traceback
import weakref
from collections.abc import AsyncIterator, Coroutine, Generator, Iterator, Mapping
from dataclasses import dataclass
from functools import partial, wraps
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Generic,
    Optional,
    Protocol,
    TypedDict,
    TypeVar,
    cast,
    overload,
    runtime_checkable,
)

from typing_extensions import ParamSpec

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


S = TypeVar("S")
V = TypeVar("V")

P = ParamSpec("P")
R = TypeVar("R")


if sys.version_info < (3, 10):

    def aiter(obj: AsyncIterator[V]) -> AsyncIterator[V]:
        return obj.__aiter__()

    async def anext(obj: AsyncIterator[V], default: Optional[V] = None) -> V:  # noqa: UP007,UP045
        try:
            return await obj.__anext__()
        except StopAsyncIteration:
            if default is not None:
                return default
            else:
                raise


logger = logging.getLogger(__name__)


CALL_CREATE_MSG = "Error creating call:\n{}"
ASYNC_CALL_CREATE_MSG = "Error creating async call:\n{}"
ON_OUTPUT_MSG = "Error capturing call output:\n{}"
UNINITIALIZED_MSG = "Warning: Traces will not be logged. Call weave.init to log your traces to a project.\n"


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
    resolve_fn: Callable[P, R]

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

    # __call__: Callable[..., Any]
    @overload
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...
    @overload
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...  # pyright: ignore[reportOverlappingOverload]

    __self__: Any

    # `_tracing_enabled` is a runtime-only flag that can be used to disable
    # call tracing for an op. It is not persisted as a property of the op, but is
    # respected by the current execution context. It is an underscore property
    # because it is not intended to be used by users directly, but rather assists
    # with internal Weave behavior. If we find a need to expose this to users, we
    # should consider a more user-friendly API (perhaps a setter/getter) & whether
    # it disables child ops as well.
    _tracing_enabled: bool

    # `_code_capture_enabled` is a  flag that can be used to disable code capture
    # for an op.  This is currently used in imperative evaluations to prevent
    # unwanted code versioning using our code capture system.
    _code_capture_enabled: bool

    tracing_sample_rate: float


def _set_on_input_handler(func: Op, on_input: OnInputHandlerType) -> None:
    if func._on_input_handler is not None:
        raise ValueError("Cannot set on_input_handler multiple times")
    func._on_input_handler = on_input


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


class OpCallError(Exception): ...


def _default_on_input_handler(func: Op, args: tuple, kwargs: dict) -> ProcessedInputs:
    try:
        sig = inspect.signature(func)
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
    func: Op, *args: Any, __weave: WeaveKwargs | None = None, **kwargs: Any
) -> Call:
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


def is_tracing_setting_disabled() -> bool:
    if settings.should_disable_weave():
        return True
    if weave_client_context.get_weave_client() is None:
        log_once(logger.warn, UNINITIALIZED_MSG)
        return True
    if not get_tracing_enabled():
        return True
    return False


def should_skip_tracing_for_op(op: Op) -> bool:
    return not op._tracing_enabled


def _should_sample_traces(op: Op) -> bool:
    if call_context.get_current_call():
        return False  # Don't sample traces for child calls

    if random.random() > op.tracing_sample_rate:
        return True  # Sample traces for this call

    return False


def placeholder_call() -> Call:
    # Import here to avoid circular dependency
    from weave.trace.weave_client import NoOpCall

    return NoOpCall()


def is_placeholder_call(call: Call) -> bool:
    from weave.trace.weave_client import NoOpCall

    return isinstance(call, NoOpCall)


def _call_sync_func(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    # When this param is True, calls do not automatically "finish" when the function
    # returns.  The user must explicitly call `finish` on the call object.  This is
    # included to support the imperative evaluation logging interface.
    __require_explicit_finish: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
    func = op.resolve_fn
    call = placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if is_tracing_setting_disabled() or should_skip_tracing_for_op(op):
        res = func(*args, **kwargs)
        call.output = res
        return res, call

    if _should_sample_traces(op):
        with tracing_disabled():
            res = func(*args, **kwargs)
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
        res = func(*args, **kwargs)
        return res, call

    # Execute the op and process the result
    client = weave_client_context.require_weave_client()
    has_finished = False

    def finish(output: Any = None, exception: BaseException | None = None) -> None:
        if __require_explicit_finish:
            return

        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")

        client.finish_call(
            call,
            output,
            exception,
            op=op,
        )

    def on_output(output: Any) -> Any:
        if handler := getattr(op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    try:
        res = func(*args, **kwargs)
    except Exception as e:
        finish(exception=e)
        if __should_raise:
            raise
        return None, call

    res = box.box(res)
    try:
        # Here we do a try/catch because we don't want to
        # break the user process if we trip up on processing
        # the output
        res = on_output(res)
    except Exception:
        if get_raise_on_captured_errors():
            raise
        log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))
    finally:
        # Is there a better place for this? We want to ensure that even
        # if the final output fails to be captured, we still pop the call
        # so we don't put future calls under the old call.
        call_context.pop_call(call.id)

    return res, call


async def _call_async_func(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    __require_explicit_finish: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
    func = op.resolve_fn
    call = placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if is_tracing_setting_disabled() or should_skip_tracing_for_op(op):
        res = await func(*args, **kwargs)
        call.output = res
        return res, call

    if _should_sample_traces(op):
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
        return res, call

    # Execute the op and process the result
    client = weave_client_context.require_weave_client()
    has_finished = False

    def finish(output: Any = None, exception: BaseException | None = None) -> None:
        if __require_explicit_finish:
            return

        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")

        client.finish_call(
            call,
            output,
            exception,
            op=op,
        )

    def on_output(output: Any) -> Any:
        if handler := getattr(op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    try:
        res = await func(*args, **kwargs)
    except Exception as e:
        finish(exception=e)
        if __should_raise:
            raise
        return None, call

    res = box.box(res)
    try:
        # Here we do a try/catch because we don't want to
        # break the user process if we trip up on processing
        # the output
        res = on_output(res)
    except Exception:
        if get_raise_on_captured_errors():
            raise
        log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))
    finally:
        # Is there a better place for this? We want to ensure that even
        # if the final output fails to be captured, we still pop the call
        # so we don't put future calls under the old call.
        call_context.pop_call(call.id)

    return res, call


def call(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    # When this param is True, calls do not automatically "finish" when the function
    # returns.  The user must explicitly call `finish` on the call object.  This is
    # included to support the imperative evaluation logging interface.
    __require_explicit_finish: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
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
    if inspect.iscoroutinefunction(op.resolve_fn):
        return _call_async_func(
            op,
            *args,
            __weave=__weave,
            __should_raise=__should_raise,
            __require_explicit_finish=__require_explicit_finish,
            **kwargs,
        )
    else:
        return _call_sync_func(
            op,
            *args,
            __weave=__weave,
            __should_raise=__should_raise,
            __require_explicit_finish=__require_explicit_finish,
            **kwargs,
        )


def calls(op: Op) -> CallsIter:
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
    func: Callable[P, R],
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
) -> Op[P, R]: ...


@overload
def op(
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
) -> Callable[[Callable[P, R]], Op[P, R]]: ...


@overload
def op(
    *,
    name: str | None = None,
    enable_code_capture: bool = True,
) -> Callable[[Callable[P, R]], Op[P, R]]: ...


def op(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    tracing_sample_rate: float = 1.0,
    enable_code_capture: bool = True,
) -> Callable[[Callable[P, R]], Op[P, R]] | Op[P, R]:
    """
    A decorator to weave op-ify a function or method. Works for both sync and async.
    Automatically detects iterator functions and applies appropriate behavior.
    """
    if not isinstance(tracing_sample_rate, (int, float)):
        raise TypeError("tracing_sample_rate must be a float")
    if not 0 <= tracing_sample_rate <= 1:
        raise ValueError("tracing_sample_rate must be between 0 and 1")

    def op_deco(func: Callable[P, R]) -> Op[P, R]:
        # Check function type
        is_method = _is_unbound_method(func)
        is_async = inspect.iscoroutinefunction(func)
        is_generator = inspect.isgeneratorfunction(func)
        is_async_generator = inspect.isasyncgenfunction(func)

        # Create the appropriate wrapper based on function type
        def create_wrapper(func: Callable[P, R]) -> Op[P, R]:
            if is_async:

                @wraps(func)
                async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportRedeclaration]
                    res, _ = await _call_async_func(
                        cast(Op, wrapper), *args, __should_raise=True, **kwargs
                    )
                    return cast(R, res)
            else:

                @wraps(func)
                def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    res, _ = _call_sync_func(
                        cast(Op, wrapper), *args, __should_raise=True, **kwargs
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
            wrapper._code_capture_enabled = enable_code_capture  # type: ignore

            if callable(call_display_name):
                params = inspect.signature(call_display_name).parameters
                if len(params) != 1:
                    raise DisplayNameFuncError(
                        "`call_display_name` function must take exactly 1 argument (the Call object)"
                    )
            wrapper.call_display_name = call_display_name  # type: ignore

            # Mark what type of function this is for runtime type checking
            wrapper._is_async = is_async  # type: ignore
            wrapper._is_generator = is_generator  # type: ignore
            wrapper._is_async_generator = is_async_generator  # type: ignore

            return cast(Op[P, R], wrapper)

        # Create the wrapper
        return create_wrapper(func)

    if func is None:
        return op_deco
    return op_deco(func)


def get_captured_code(op: Op) -> str:
    """Get the captured code of the op.

    This only works when you get an op back from a ref.  The pattern is:

    ref = weave.publish(func)
    op = ref.get()
    captured_code = op.get_captured_code()
    """
    try:
        return op.art.path_contents["obj.py"].decode()  # type: ignore
    except Exception:
        raise RuntimeError(
            "Failed to get captured code for op (this only works when you get an op back from a ref)."
        )


def maybe_bind_method(func: Callable, self: Any = None) -> Callable | MethodType:
    """Bind a function to any object (even if it's not a class)

    If self is None, return the function as is.
    """
    if (sig := inspect.signature(func)) and sig.parameters.get("self"):
        if inspect.ismethod(func) and id(func.__self__) != id(self):
            raise ValueError("Cannot re-bind a method to an new object")
        return MethodType(func, self)
    return func


def maybe_unbind_method(oplike: Op | MethodType | partial) -> Op:
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
    """Check if an object is an Op."""
    if sys.version_info < (3, 12):
        return isinstance(obj, Op)

    return all(hasattr(obj, attr) for attr in Op.__annotations__)


def as_op(fn: Callable[P, R]) -> Op[P, R]:
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

    # The unbinding is necessary for methods because `MethodType` is applied after the
    # func is decorated into an Op.
    return cast(Op[P, R], maybe_unbind_method(cast(Op, fn)))


_OnYieldType = Callable[[V], None]
_OnErrorType = Callable[[Exception], None]
_OnCloseType = Callable[[], None]
ON_CLOSE_MSG = "Error closing iterator, call data may be incomplete:\n{}"
ON_ERROR_MSG = "Error capturing error from iterator, call data may be incomplete:\n{}"
ON_YIELD_MSG = "Error capturing value from iterator, call data may be incomplete:\n{}"
ON_AYIELD_MSG = (
    "Error capturing async value from iterator, call data may be incomplete:\n{}"
)


class _IteratorWrapper(Generic[V]):
    """This class wraps an iterator object allowing hooks to be added to the lifecycle of the iterator. It is likely
    that this class will be helpful in other contexts and might be moved to a more general location in the future.
    """

    def __init__(
        self,
        iterator_or_ctx_manager: Iterator | AsyncIterator,
        on_yield: _OnYieldType,
        on_error: _OnErrorType,
        on_close: _OnCloseType,
    ) -> None:
        self._iterator_or_ctx_manager = iterator_or_ctx_manager
        self._on_yield = on_yield
        self._on_error = on_error
        self._on_close = on_close
        self._on_finished_called = False

        atexit.register(weakref.WeakMethod(self._call_on_close_once))

    def _call_on_close_once(self) -> None:
        if not self._on_finished_called:
            try:
                self._on_close()  # type: ignore
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_CLOSE_MSG.format(traceback.format_exc()))
            self._on_finished_called = True

    def _call_on_error_once(self, e: Exception) -> None:
        if not self._on_finished_called:
            try:
                self._on_error(e)
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_ERROR_MSG.format(traceback.format_exc()))
            self._on_finished_called = True

    def __iter__(self) -> _IteratorWrapper:
        return self

    def __next__(self) -> Generator[None, None, V]:
        if not hasattr(self._iterator_or_ctx_manager, "__next__"):
            try:
                # This is kept as a type ignore because the `google-generativeai` pkg seems
                # to yield an object that has properties of both value and iterator, but doesn't
                # seem to pass the isinstance(obj, Iterator) check...
                self._iterator_or_ctx_manager = iter(self._iterator_or_ctx_manager)  # type: ignore
            except TypeError:
                raise TypeError(
                    f"Cannot call next on an object of type {type(self._iterator_or_ctx_manager)}"
                )
        try:
            value = next(self._iterator_or_ctx_manager)  # type: ignore
            try:
                # Here we do a try/catch because we don't want to
                # break the user process if we trip up on processing
                # the yielded value
                self._on_yield(value)
            except Exception as e:
                # We actually use StopIteration to signal the end of the iterator
                # in some cases (like when we don't want to surface the last chunk
                # with usage info from openai integration).
                if isinstance(e, (StopAsyncIteration, StopIteration)):
                    raise
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_YIELD_MSG.format(traceback.format_exc()))
        except (StopIteration, StopAsyncIteration) as e:
            self._call_on_close_once()
            raise
        except Exception as e:
            self._call_on_error_once(e)
            raise
        else:
            return value

    def __aiter__(self) -> _IteratorWrapper:
        return self

    async def __anext__(self) -> Generator[None, None, V]:
        if not hasattr(self._iterator_or_ctx_manager, "__anext__"):
            try:
                # This is kept as a type ignore because the `google-generativeai` pkg seems
                # to yield an object that has properties of both value and iterator, but doesn't
                # seem to pass the isinstance(obj, Iterator) check...
                self._iterator_or_ctx_manager = aiter(self._iterator_or_ctx_manager)  # type: ignore
            except TypeError:
                raise TypeError(
                    f"Cannot call anext on an object of type {type(self._iterator_or_ctx_manager)}"
                )
        try:
            value = await self._iterator_or_ctx_manager.__anext__()  # type: ignore
            try:
                self._on_yield(value)
                # Here we do a try/catch because we don't want to
                # break the user process if we trip up on processing
                # the yielded value
            except Exception as e:
                # We actually use StopIteration to signal the end of the iterator
                # in some cases (like when we don't want to surface the last chunk
                # with usage info from openai integration).
                if isinstance(e, (StopAsyncIteration, StopIteration)):
                    raise
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_AYIELD_MSG.format(traceback.format_exc()))
        except (StopAsyncIteration, StopIteration) as e:
            self._call_on_close_once()
            raise StopAsyncIteration
        except Exception as e:
            self._call_on_error_once(e)
            raise
        else:
            return value

    def __del__(self) -> None:
        self._call_on_close_once()

    def close(self) -> None:
        self._call_on_close_once()

    def __getattr__(self, name: str) -> Any:
        """Delegate all other attributes to the wrapped iterator."""
        if name in [
            "_iterator_or_ctx_manager",
            "_on_yield",
            "_on_error",
            "_on_close",
            "_on_finished_called",
            "_call_on_error_once",
        ]:
            return object.__getattribute__(self, name)
        return getattr(self._iterator_or_ctx_manager, name)

    def __enter__(self) -> _IteratorWrapper:
        if hasattr(self._iterator_or_ctx_manager, "__enter__"):
            # let's enter the context manager to get the stream iterator
            self._iterator_or_ctx_manager = self._iterator_or_ctx_manager.__enter__()
        return self

    def __exit__(
        self,
        exc_type: Exception | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        if exc_type and isinstance(exc_value, Exception):
            self._call_on_error_once(exc_value)
        if hasattr(
            self._iterator_or_ctx_manager, "__exit__"
        ):  # case where is a context mngr
            self._iterator_or_ctx_manager.__exit__(exc_type, exc_value, traceback)
        self._call_on_close_once()

    async def __aenter__(self) -> _IteratorWrapper:
        if hasattr(
            self._iterator_or_ctx_manager, "__aenter__"
        ):  # let's enter the context manager
            self._iterator_or_ctx_manager = (
                await self._iterator_or_ctx_manager.__aenter__()
            )
        return self

    async def __aexit__(
        self,
        exc_type: Exception | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        if exc_type and isinstance(exc_value, Exception):
            self._call_on_error_once(exc_value)
        self._call_on_close_once()


class _Accumulator(Generic[S, V]):
    state: S | None

    def __init__(
        self,
        accumulator: Callable[[S | None, V], S],
        initial_state: S | None = None,
    ):
        self._accumulator = accumulator
        self._state = initial_state

    def next(self, value: V) -> None:
        # the try-except hack to catch `StopIteration` inside `<integration>_accumulator`
        # this `StopIteration` is raised when some condition is met, for example, when
        # we don't want to surface last chunk (with usage info) from openai integration.
        try:
            self._state = self._accumulator(self._state, value)
        except StopIteration as e:
            self._state = e.value
            raise

    def get_state(self) -> S | None:
        return self._state


def _build_iterator_from_accumulator_for_op(
    value: Iterator[V],
    accumulator: Callable,
    on_finish: FinishCallbackType,
    iterator_wrapper: type[_IteratorWrapper] = _IteratorWrapper,
) -> _IteratorWrapper:
    acc: _Accumulator = _Accumulator(accumulator)

    def on_yield(value: V) -> None:
        acc.next(value)

    def on_error(e: Exception) -> None:
        on_finish(acc.get_state(), e)

    def on_close() -> None:
        on_finish(acc.get_state(), None)

    return iterator_wrapper(value, on_yield, on_error, on_close)


def _add_accumulator(
    op: Op,
    make_accumulator: Callable[[dict], Callable[[S, V], S]],
    *,
    should_accumulate: Callable[[dict], bool] | None = None,
    on_finish_post_processor: Callable[[Any], Any] | None = None,
    iterator_wrapper: type[_IteratorWrapper] = _IteratorWrapper,
) -> Op:
    """This is to be used internally only - specifically designed for integrations with streaming libraries.

    Add an accumulator to an op. The accumulator will be called with the output of the op
    after the op is resolved. The accumulator should return the output of the op. This is intended
    for internal use only and may change in the future. The accumulator should take two arguments:
    the current state of the accumulator and the value to accumulate. It should return the new state
    of the accumulator. The first time the accumulator is called, the current state will be None.

    The intended usage is:

    ```
    @weave.op()
    def fn():
        size = 10
        while size > 0:
            size -= 1
            yield size

    def simple_list_accumulator(acc, value):
        if acc is None:
            acc = []
        acc.append(value)
        return acc
    add_accumulator(fn, simple_list_accumulator) # returns the op with `list(range(9, -1, -1))` as output
    """

    def on_output(
        value: Iterator[V], on_finish: FinishCallbackType, inputs: dict
    ) -> Iterator:
        def wrapped_on_finish(value: Any, e: BaseException | None = None) -> None:
            if on_finish_post_processor is not None:
                value = on_finish_post_processor(value)
            on_finish(value, e)

        if should_accumulate is None or should_accumulate(inputs):
            # we build the accumulator here dependent on the inputs (optional)
            accumulator = make_accumulator(inputs)
            return _build_iterator_from_accumulator_for_op(
                value,
                accumulator,
                wrapped_on_finish,
                iterator_wrapper,
            )
        else:
            wrapped_on_finish(value)
            return value

    op._set_on_output_handler(on_output)
    return op


__docspec__ = [call, calls]
