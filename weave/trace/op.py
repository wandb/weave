"""Defines the Op protocol and related functions."""

from __future__ import annotations

import inspect
import logging
import random
import sys
import traceback
from collections.abc import Coroutine, Mapping, Iterable, AsyncIterable
from dataclasses import dataclass
from functools import partial, wraps
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Protocol,
    TypedDict,
    cast,
    overload,
    runtime_checkable,
    TypeVar,
    Dict,
    Generic,
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
from weave.trace.errors import OpCallError
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


# Type variables for generic hooks
Input = TypeVar("Input")  # Input type
Output = TypeVar("Output")  # Output type 
State = TypeVar("State")  # State type

class OpLifecycle(Protocol[Input, Output, State]):
    """Protocol defining the lifecycle hooks for an Op.
    
    The lifecycle is:
    1. before_call - Called before the function is executed
    2. process_inputs_for_logging - Process inputs for logging purposes only
    3. on_yield - Called for each value yielded (for iterators)
    4. process_output - Process output after function execution
    5. on_error - Called when an error occurs
    6. on_finish - Called when execution finishes (success or error)
    7. after_call - Called after everything is done
    """
    
    def before_call(self, args: tuple, kwargs: dict) -> None:
        """Called before function execution."""
        ...
        
    def process_inputs_for_logging(self, args: tuple, kwargs: dict) -> dict[str, Any]:
        """Process inputs for logging purposes only. Does not affect function execution.
        
        This hook allows you to modify how inputs are logged to Weave without affecting
        the actual function execution. The original args/kwargs are passed to the function.
        
        Returns:
            A dictionary of inputs to log to Weave
        """
        ...
        
    def on_yield(self, value: Any) -> Any:
        """Called for each value yielded by an iterator."""
        ...
        
    def process_output(self, output: Any) -> Any:
        """Process output after function execution."""
        ...
        
    def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
        ...
        
    def on_finish(self, output: Any, error: Exception | None = None) -> None:
        """Called when execution finishes."""
        ...
        
    def after_call(self, call: "Call") -> None:
        """Called after everything is done."""
        ...

class DefaultOpLifecycle:
    """Default lifecycle implementation that maintains compatibility."""

    def before_call(self, call: Call) -> None:
        """Default no-op before call."""
        pass

    def process_inputs_for_logging(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Default input processing that returns inputs as is."""
        return inputs

    def on_yield(self, value: Any) -> Any:
        """Default yield processing that returns value as is."""
        return value

    def process_output(self, output: Any) -> Any:
        """Default output processing that returns output as is."""
        return output

    def on_error(self, error: Exception) -> None:
        """Default no-op error handler."""
        pass

    def on_finish(self, error: Optional[Exception]) -> None:
        """Default no-op finish handler."""
        pass

    def after_call(self, call: Call) -> None:
        """Default no-op after call."""
        pass

class IteratorLifecycle(Generic[State]):
    """Lifecycle implementation for iterators that supports accumulation."""

    def __init__(self):
        self._accumulator = None
        self._state = None
        self._on_finish = None
        self._has_finished = False

    def before_call(self, call: Call) -> None:
        """Initialize state before call."""
        self._state = None
        self._has_finished = False

    def process_inputs_for_logging(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process inputs for logging."""
        return inputs

    def on_yield(self, value: Any) -> Any:
        """Process yielded value and update state."""
        if self._accumulator is not None:
            self._state = self._accumulator(self._state, value)
        return value

    def process_output(self, output: Any) -> Any:
        """Process final output."""
        return output

    def on_error(self, error: Exception) -> None:
        """Handle error."""
        pass

    def on_finish(self, error: Optional[Exception]) -> None:
        """Handle finish with optional error."""
        if not self._has_finished and self._on_finish is not None:
            self._on_finish(self._state, error)
        self._has_finished = True

    def after_call(self, call: Call) -> None:
        """Ensure finish is called."""
        if not self._has_finished and self._on_finish is not None:
            self._on_finish(self._state, None)
            self._has_finished = True

    def add_accumulator(
        self,
        accumulator: Callable[[Optional[State], Any], State],
        on_finish: Optional[Callable[[Optional[State], Optional[Exception]], None]] = None,
    ) -> None:
        """Add accumulator function to lifecycle.

        Args:
            accumulator: Function that takes current state and yielded value and returns new state
            on_finish: Optional callback when iteration finishes
        """
        self._accumulator = accumulator
        self._on_finish = on_finish

@runtime_checkable
class Op(Protocol):
    """Protocol for Op-ified functions and methods."""
    name: str
    call_display_name: str | Callable[[Call], str]
    ref: ObjectRef | None
    resolve_fn: Callable
    lifecycle: OpLifecycle
    
    postprocess_inputs: Callable[[dict[str, Any]], dict[str, Any]] | None
    postprocess_output: Callable[..., Any] | None

    call: Callable[..., CallsIter]

    _tracing_enabled: bool
    tracing_sample_rate: float

    __call__: Callable[..., Any]
    __self__: Any


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
    from weave.trace.serialize import dictify

    attributes = dictify(attributes)

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        # Very important for `call_time_display_name` to take precedence over `func.call_display_name`
        display_name=call_time_display_name or func.call_display_name,
        attributes=attributes,
    )


def execute_op(
    op: Op,
    call: Call,
    args: tuple,
    kwargs: dict,
    should_raise: bool = True,
) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
    """Execute an op with full lifecycle hooks.

    This is the main entry point for op execution. It handles both sync and async
    functions, and manages the entire lifecycle of the op execution including:
    - Input processing for logging
    - Function execution
    - Output processing
    - Error handling
    - Iterator wrapping
    - Cleanup

    Args:
        op: The op to execute
        call: The call object representing this execution
        args: Positional arguments to pass to the function
        kwargs: Keyword arguments to pass to the function
        should_raise: Whether to raise exceptions or return them

    Returns:
        A tuple of (result, call) or a coroutine that will return that tuple
    """
    client = weave_client_context.require_weave_client()

    # Step 1: Before call hook
    op.lifecycle.before_call(call)

    # Step 2: Process inputs for logging
    try:
        inputs_dict = {
            f"arg{i}": arg for i, arg in enumerate(args)
        }
        inputs_dict.update(kwargs)
        processed_inputs = op.lifecycle.process_inputs_for_logging(inputs_dict)
        call.update_inputs(processed_inputs)
    except Exception as e:
        # Log error but continue execution
        logger.error(f"Error processing inputs for logging: {e}")

    async def _execute_async() -> tuple[Any, Call]:
        try:
            # Step 3: Execute function with original args
            if inspect.isasyncgenfunction(op.resolve_fn):
                # Handle async generator functions
                result = op.resolve_fn(*args, **kwargs)
                values = []
                try:
                    async for value in result:
                        processed = op.lifecycle.on_yield(value)
                        values.append(processed)
                except Exception as e:
                    op.lifecycle.on_error(e)
                    if should_raise:
                        raise
                finally:
                    op.lifecycle.on_finish(None)

                async def yield_from_list():
                    for value in values:
                        yield value

                result = yield_from_list()
            else:
                # Handle regular async functions
                result = await op.resolve_fn(*args, **kwargs)
                if isinstance(result, AsyncIterable):
                    # Handle async iterables
                    values = []
                    try:
                        async for value in result:
                            processed = op.lifecycle.on_yield(value)
                            values.append(processed)
                    except Exception as e:
                        op.lifecycle.on_error(e)
                        if should_raise:
                            raise
                    finally:
                        op.lifecycle.on_finish(None)

                    async def yield_from_list():
                        for value in values:
                            yield value

                    result = yield_from_list()
                else:
                    result = op.lifecycle.process_output(result)
                    op.lifecycle.on_finish(None)

            # Update call output
            call.update_output(result)
            op.lifecycle.after_call(call)
            return result, call

        except Exception as e:
            # Step 5: Finish with error
            op.lifecycle.on_error(e)
            op.lifecycle.on_finish(e)
            op.lifecycle.after_call(call)
            if should_raise:
                raise
            return e, call

    def _execute_sync() -> tuple[Any, Call]:
        try:
            # Step 3: Execute function with original args
            result = op.resolve_fn(*args, **kwargs)

            # Step 4: Process output
            if inspect.isgenerator(result):
                # Handle sync iterators
                values = []
                try:
                    for value in result:
                        processed = op.lifecycle.on_yield(value)
                        values.append(processed)
                except Exception as e:
                    op.lifecycle.on_error(e)
                    if should_raise:
                        raise
                finally:
                    op.lifecycle.on_finish(None)

                def yield_from_list():
                    for value in values:
                        yield value

                result = yield_from_list()
            elif isinstance(result, Iterable) and not isinstance(result, (str, bytes)):
                # Handle other iterables
                values = []
                try:
                    for value in result:
                        processed = op.lifecycle.on_yield(value)
                        values.append(processed)
                except Exception as e:
                    op.lifecycle.on_error(e)
                    if should_raise:
                        raise
                finally:
                    op.lifecycle.on_finish(None)

                def yield_from_list():
                    for value in values:
                        yield value

                result = yield_from_list()
            else:
                result = op.lifecycle.process_output(result)
                op.lifecycle.on_finish(None)

            # Update call output
            call.update_output(result)
            op.lifecycle.after_call(call)
            return result, call

        except Exception as e:
            # Step 5: Finish with error
            op.lifecycle.on_error(e)
            op.lifecycle.on_finish(e)
            op.lifecycle.after_call(call)
            if should_raise:
                raise
            return e, call

    if inspect.iscoroutinefunction(op.resolve_fn) or inspect.isasyncgenfunction(op.resolve_fn):
        return _execute_async()
    else:
        return _execute_sync()


def call(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
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
        return _do_call_async(
            op,
            *args,
            __weave=__weave,
            __should_raise=__should_raise,
            **kwargs,
        )
    else:
        return _do_call(
            op,
            *args,
            __weave=__weave,
            __should_raise=__should_raise,
            **kwargs,
        )


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
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
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
        execute_result = execute_op(
            op, call, *pargs.args, __should_raise=__should_raise, **pargs.kwargs
        )
        if inspect.iscoroutine(execute_result):
            raise TypeError(
                "Internal error: Expected `execute_op` to return a sync result"
            )
        execute_result = cast(tuple[Any, "Call"], execute_result)
        res, call = execute_result
    return res, call


async def _do_call_async(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
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
        execute_result = execute_op(
            op, call, *args, __should_raise=__should_raise, **kwargs
        )
        if not inspect.iscoroutine(execute_result):
            raise TypeError(
                "Internal error: Expected `execute_op` to return a coroutine"
            )
        res, call = await execute_result
    return res, call


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
    func: Callable,
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
) -> Op: ...


@overload
def op(
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
) -> Callable[[Callable], Op]: ...


def op(
    func: Callable | None = None,
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    tracing_sample_rate: float = 1.0,
) -> Callable[[Callable], Op] | Op:
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
            object and returns a string.
        postprocess_inputs (Optional[Callable[[dict[str, Any]], dict[str, Any]]]): A function
            to process the inputs after they've been captured but before they're logged.
        postprocess_output (Optional[Callable[..., Any]]): A function to process the output
            after it's been returned from the function but before it's logged.
        tracing_sample_rate (float): The sampling rate for tracing this function. Defaults to 1.0.

    Returns:
        Union[Callable[[Any], Op], Op]: If called without arguments, returns a decorator.
        If called with a function, returns the decorated function as an Op.
    """
    if not isinstance(tracing_sample_rate, (int, float)):
        raise TypeError("tracing_sample_rate must be a float")
    if not 0 <= tracing_sample_rate <= 1:
        raise ValueError("tracing_sample_rate must be between 0 and 1")

    def op_deco(func: Callable) -> Op:
        # Check function type
        is_method = _is_unbound_method(func)
        is_async = inspect.iscoroutinefunction(func)

        def create_wrapper(func: Callable) -> Op:
            if is_async:
                @wraps(func)
                async def wrapper(*args: Any, **kwargs: Any) -> Any:
                    res, _ = await execute_op(
                        cast(Op, wrapper),
                        _placeholder_call(),
                        args,
                        kwargs,
                        should_raise=True,
                    )
                    return res
            else:
                @wraps(func)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    res, _ = execute_op(
                        cast(Op, wrapper),
                        _placeholder_call(),
                        args,
                        kwargs,
                        should_raise=True,
                    )
                    return res

            # Initialize the wrapper with required Op attributes
            wrapper.resolve_fn = func
            wrapper.name = name or (func.__qualname__ if is_method else func.__name__)
            wrapper.ref = None
            wrapper.lifecycle = DefaultOpLifecycle()
            wrapper.postprocess_inputs = postprocess_inputs
            wrapper.postprocess_output = postprocess_output
            wrapper.call = partial(call, wrapper)
            wrapper.calls = partial(calls, wrapper)
            wrapper.__call__ = wrapper
            wrapper.__self__ = wrapper
            wrapper._tracing_enabled = True
            wrapper.tracing_sample_rate = tracing_sample_rate

            if callable(call_display_name):
                params = inspect.signature(call_display_name).parameters
                if len(params) != 1:
                    raise DisplayNameFuncError(
                        "`call_display_name` function must take exactly 1 argument (the Call object)"
                    )
            wrapper.call_display_name = call_display_name

            return cast(Op, wrapper)

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

    # The unbinding is necessary for methods because `MethodType` is applied after the
    # func is decorated into an Op.
    return maybe_unbind_method(cast(Op, fn))


def add_accumulator(
    op: Op,
    make_accumulator: Callable[[dict], Callable[[S, V], S]],
    *,
    should_accumulate: Callable[[dict], bool] | None = None,
    on_finish_post_processor: Callable[[Any], Any] | None = None,
) -> Op:
    """Add accumulator functionality to an op.
    
    This replaces the old accumulator implementation with one that uses the lifecycle hooks.
    The accumulator will be called with each yielded value and can maintain state.
    
    Args:
        op: The op to add accumulator to
        make_accumulator: Function that creates an accumulator function
        should_accumulate: Optional function to determine if accumulation should happen
        on_finish_post_processor: Optional function to process final state
        
    Returns:
        The op with accumulator functionality added
    """
    def wrapped_on_finish(value: Any, error: BaseException | None = None) -> None:
        if on_finish_post_processor is not None:
            value = on_finish_post_processor(value)
        if hasattr(op.lifecycle, "_on_finish"):
            op.lifecycle._on_finish(value, error)
            
    # Create iterator lifecycle
    iterator_lifecycle = IteratorLifecycle()
    iterator_lifecycle._on_finish = wrapped_on_finish
    
    # Only set accumulator if should_accumulate passes
    if should_accumulate is None or should_accumulate({}):
        iterator_lifecycle._accumulator = make_accumulator({})
        
    # Replace existing lifecycle
    op.lifecycle = iterator_lifecycle
    return op


__docspec__ = [call, calls]
