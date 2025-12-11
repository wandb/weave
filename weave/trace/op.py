"""Defines the Op protocol and related functions."""

from __future__ import annotations

import atexit
import inspect
import logging
import random
import sys
import traceback
import weakref
from collections import defaultdict
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Coroutine,
    Generator,
    Iterator,
    Mapping,
)
from dataclasses import dataclass
from functools import partial, wraps
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    TypedDict,
    TypeVar,
    cast,
    overload,
)

from typing_extensions import ParamSpec, TypeIs, Unpack

from weave.trace import box, settings
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.context.call_context import (
    call_attributes,
    get_tracing_enabled,
    tracing_disabled,
)
from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.op_protocol import (
    CallDisplayNameFunc,
    FinishCallbackType,
    OnFinishHandlerType,
    OnInputHandlerType,
    OnOutputHandlerType,
    Op,
    PostprocessInputsFunc,
    PostprocessOutputFunc,
    ProcessedInputs,
)
from weave.trace.util import log_once

if TYPE_CHECKING:
    from weave.trace.call import Call, CallsIter, NoOpCall

S = TypeVar("S")
V = TypeVar("V")

P = ParamSpec("P")
R = TypeVar("R")


logger = logging.getLogger(__name__)


CALL_CREATE_MSG = "Error creating call:\n{}"
ASYNC_CALL_CREATE_MSG = "Error creating async call:\n{}"
ON_OUTPUT_MSG = "Error capturing call output:\n{}"
UNINITIALIZED_MSG = "Warning: Traces will not be logged. Call weave.init to log your traces to a project.\n"


class DisplayNameFuncError(ValueError): ...


class OpCallError(Exception): ...


# Call, original function output, exception if occurred


# Cache for package sentinel values to avoid repeated imports
_SENTINEL_CACHE: dict[Sentinel, Any] = {}


@dataclass(frozen=True)
class Sentinel:
    package: str
    path: str
    name: str


_sentinels_to_check = [
    Sentinel(package="openai", path="openai._types", name="NOT_GIVEN"),
    Sentinel(package="openai", path="openai._types", name="omit"),
    Sentinel(
        package="openai", path="openai._types", name="Omit"
    ),  # Class, not instance
    Sentinel(package="cohere", path="cohere.base_client", name="COHERE_NOT_GIVEN"),
    Sentinel(package="anthropic", path="anthropic._types", name="NOT_GIVEN"),
    Sentinel(package="cerebras", path="cerebras.cloud.sdk._types", name="NOT_GIVEN"),
]


def _check_param_is_sentinel(param: inspect.Parameter, sentinel: Sentinel) -> bool:
    """Check if param_default is a sentinel from a specific package.

    Only imports the sentinel if:
    1. The package is already imported in sys.modules
    2. We haven't cached this sentinel yet

    Args:
        package_name: Name of the package to check (e.g., "openai")
        import_path: Full import path for the sentinel (e.g., "openai._types")
        sentinel_name: Name of the sentinel constant (e.g., "NOT_GIVEN")
        param_default: The default value to check

    Returns:
        True if param_default is the sentinel from this package, False otherwise
    """
    if sentinel in _SENTINEL_CACHE:
        return param.default is _SENTINEL_CACHE[sentinel]

    if sentinel.package in sys.modules:
        try:
            module = __import__(sentinel.path, fromlist=[sentinel.name])
            sentinel_value = getattr(module, sentinel.name)
            _SENTINEL_CACHE[sentinel] = sentinel_value
            if param.default is sentinel_value:
                return True
        except (ImportError, AttributeError):
            _SENTINEL_CACHE[sentinel] = None
    return False


def _value_is_sentinel(param: inspect.Parameter) -> bool:
    # Always check for None and Ellipsis using identity check
    if param.default is None or param.default is Ellipsis:
        return True

    # Check cached sentinels first
    for sentinel in _SENTINEL_CACHE.values():
        if sentinel is not None:
            # Check for identity (singleton instances)
            if param.default is sentinel:
                return True
            # Check for isinstance (e.g., openai.Omit class instances)
            if isinstance(sentinel, type) and isinstance(param.default, sentinel):
                return True

    for sentinel in _sentinels_to_check:
        if _check_param_is_sentinel(param, sentinel):
            return True

    return False


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
    attributes: dict[str, Any]
    call_id: str | None


class OpKwargs(TypedDict, total=False):
    """TypedDict for op() keyword arguments."""

    name: str | None
    call_display_name: str | CallDisplayNameFunc | None
    postprocess_inputs: PostprocessInputsFunc | None
    postprocess_output: PostprocessOutputFunc | None
    tracing_sample_rate: float
    enable_code_capture: bool
    accumulator: Callable[[Any | None, Any], Any] | None


def setup_dunder_weave_dict(d: WeaveKwargs | None = None) -> WeaveKwargs:
    """Sets up a __weave dict used to pass WeaveKwargs to ops."""
    res: dict[str, Any] = {}
    if d is not None:
        res = cast(dict[str, Any], d)
    res.setdefault("attributes", defaultdict(dict))
    res.setdefault("display_name", None)
    return cast(WeaveKwargs, res)


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
    """Check if a function is a function defined on a class (an "unbound" method).

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
    # Lazy load so Content modele isn't resolved until necessary
    from weave.trace.annotation_parser import (
        ContentAnnotation,
        parse_content_annotation,
        parse_from_signature,
    )
    from weave.type_wrappers import Content

    try:
        sig = inspect.signature(func)
        inputs = sig.bind(*args, **kwargs).arguments
    except TypeError as e:
        raise OpCallError(f"Error calling {func.name}: {e}") from e

    inputs_with_defaults = _apply_fn_defaults_to_inputs(func, inputs)

    # Annotated input type flow
    # If user defines postprocess_inputs manually, trust it instead of running this
    to_weave_inputs = {}
    if not func.postprocess_inputs:
        parsed_annotations = parse_from_signature(sig)
        for param_name, value in inputs_with_defaults.items():
            # Check if we found an annotation which requires substitution
            parsed = parsed_annotations.get(param_name)
            # We don't need to do anything with this if a special annotation is not found
            if not parsed:
                to_weave_inputs[param_name] = value
                continue
            elif isinstance(parsed, ContentAnnotation):
                to_weave_inputs[param_name] = Content._from_guess(
                    value, mimetype=parsed.mimetype, extension=parsed.extension
                )
    else:
        to_weave_inputs = inputs_with_defaults

    # Annotated return type flow
    # If user defines postprocess_output manually, trust it instead of running this
    if not func.postprocess_output and sig.return_annotation:
        parsed = parse_content_annotation(str(sig.return_annotation))
        if isinstance(parsed, ContentAnnotation):
            func.postprocess_output = lambda x: Content._from_guess(
                x, mimetype=parsed.mimetype, extension=parsed.extension
            )

    return ProcessedInputs(
        original_args=args,
        original_kwargs=kwargs,
        args=args,
        kwargs=kwargs,
        inputs=to_weave_inputs,
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
    call_attrs = __weave.get("attributes") if __weave else None
    preferred_call_id = __weave.get("call_id") if __weave else None

    # If/When we do memoization, this would be a good spot

    parent_call = call_context.get_current_call()

    from weave.trace.serialization.serialize import dictify

    attributes = dictify(call_attributes.get())

    if call_attrs is not None:
        attributes = {**attributes, **call_attrs}

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        # Very important for `call_time_display_name` to take precedence over `func.call_display_name`
        display_name=call_time_display_name or func.call_display_name,
        attributes=attributes,
        _call_id_override=preferred_call_id,
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
    from weave.trace.call import NoOpCall

    return NoOpCall()


def is_placeholder_call(call: Call) -> TypeIs[NoOpCall]:
    from weave.trace.call import NoOpCall

    return isinstance(call, NoOpCall)


def _set_python_function_type_on_weave_dict(
    __weave: WeaveKwargs, type_str: str
) -> None:
    weave_dict = (
        __weave.setdefault("attributes", {})
        .setdefault("weave", {})
        .setdefault("python", {})
    )
    weave_dict["type"] = type_str


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

    __weave = setup_dunder_weave_dict(__weave)
    _set_python_function_type_on_weave_dict(__weave, "function")

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
            return
        has_finished = True

        try:
            # Apply any post-processing to the accumulated state if needed
            try:
                if processor := getattr(op, "_on_finish_post_processor", None):
                    output = processor(output)
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))

            client.finish_call(
                call,
                output,
                exception,
                op=op,
            )
        finally:
            # Only pop the call context if we're the current call
            current_call = call_context.get_current_call()
            if current_call and current_call.id == call.id:
                call_context.pop_call(call.id)

    def on_output(output: Any) -> Any:
        if handler := getattr(op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)

        if (
            op._accumulator
            and isinstance(output, (Iterator, Generator, AsyncIterator))
            and not isinstance(output, (str, bytes))
        ):
            # If an accumulator is set on the op directly (e.g., via @weave.op(accumulator=...))
            # and the function returns a standard iterator/generator, or an async iterator, apply the accumulator.

            # Create an _Accumulator helper instance
            # op._accumulator is Callable[[State | None, Value], State]
            acc_logic: _Accumulator = _Accumulator(op._accumulator)

            # Define callbacks for the _IteratorWrapper
            def acc_on_yield(value: Any) -> None:
                acc_logic.next(value)

            def acc_on_error(e: Exception) -> None:
                # Call the original finish function with accumulated state and exception
                finish(acc_logic.get_state(), e)

            def acc_on_close() -> None:
                # Call the original finish function with accumulated state
                finish(acc_logic.get_state(), None)

            # Wrap the output iterator with the accumulation logic
            # _IteratorWrapper can handle sync and async iterators through its __next__ and __anext__.
            return _IteratorWrapper(output, acc_on_yield, acc_on_error, acc_on_close)

        # Original behavior: if no handler and no accumulator for an iterator,
        # or if output is not an iterator type we should accumulate.
        finish(output)
        return output

    try:
        res = func(*args, **kwargs)
    except Exception as e:
        finish(exception=e)
        if __should_raise:
            raise
        return None, call
    except (SystemExit, KeyboardInterrupt) as e:
        finish(exception=e)
        raise

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

    __weave = setup_dunder_weave_dict(__weave)
    _set_python_function_type_on_weave_dict(__weave, "async_function")

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
            return
        has_finished = True

        try:
            # Apply any post-processing to the accumulated state if needed
            try:
                if processor := getattr(op, "_on_finish_post_processor", None):
                    output = processor(output)
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))

            client.finish_call(
                call,
                output,
                exception,
                op=op,
            )
        finally:
            # Only pop the call context if we're the current call
            current_call = call_context.get_current_call()
            if current_call and current_call.id == call.id:
                call_context.pop_call(call.id)

    def on_output(output: Any) -> Any:
        if handler := getattr(op, "_on_output_handler", None):
            return handler(output, finish, call.inputs)

        if (
            op._accumulator
            and isinstance(output, AsyncIterator)
            and not isinstance(output, (str, bytes))
        ):
            acc_logic: _Accumulator = _Accumulator(op._accumulator)

            def acc_on_yield(value: Any) -> None:
                acc_logic.next(value)

            def acc_on_error(e: Exception) -> None:
                finish(acc_logic.get_state(), e)

            def acc_on_close() -> None:
                finish(acc_logic.get_state(), None)

            return _IteratorWrapper(output, acc_on_yield, acc_on_error, acc_on_close)
        else:
            finish(output)
            return output

    try:
        res = await func(*args, **kwargs)
    except Exception as e:
        finish(exception=e)
        if __should_raise:
            raise
        return None, call
    except (SystemExit, KeyboardInterrupt) as e:
        finish(exception=e)
        raise

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


def _call_sync_gen(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    __require_explicit_finish: bool = False,
    **kwargs: Any,
) -> tuple[Generator[Any], Call]:
    func = op.resolve_fn
    call = placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if should_skip_tracing_for_op(op):
        gen = func(*args, **kwargs)
        call.output = gen
        return gen, call

    if _should_sample_traces(op):
        with tracing_disabled():
            gen = func(*args, **kwargs)
            call.output = gen
            return gen, call

    __weave = setup_dunder_weave_dict(__weave)
    _set_python_function_type_on_weave_dict(__weave, "generator")

    # Proceed with tracing
    try:
        call = _create_call(op, *args, __weave=__weave, **kwargs)
    except OpCallError:
        raise
    except Exception:
        if get_raise_on_captured_errors():
            raise
        log_once(
            logger.error,
            CALL_CREATE_MSG.format(traceback.format_exc()),
        )
        gen = func(*args, **kwargs)
        return gen, call

    # Execute the op and get the generator
    client = weave_client_context.require_weave_client()
    has_finished = False
    accumulated_state = None
    acc = op._accumulator

    def finish(output: Any = None, exception: BaseException | None = None) -> None:
        if __require_explicit_finish:
            return

        nonlocal has_finished
        if has_finished:
            return
        has_finished = True

        try:
            # Apply any post-processing to the accumulated state if needed
            try:
                if processor := getattr(op, "_on_finish_post_processor", None):
                    output = processor(output)
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))

            client.finish_call(
                call,
                output,
                exception,
                op=op,
            )
        finally:
            # Only pop the call context if we're the current call
            current_call = call_context.get_current_call()
            if current_call and current_call.id == call.id:
                call_context.pop_call(call.id)

    # Create the generator wrapper
    try:
        # Define the wrapper generator that will handle the call context properly
        def wrapped_generator() -> Generator[Any]:
            nonlocal accumulated_state, has_finished

            # Set the call context before creating the original generator
            # This ensures all calls made during generator initialization are properly nested
            call_context.push_call(call)

            try:
                # Create the original generator within the proper call context
                original_gen = func(*args, **kwargs)

                # If there's an on_output_handler, let it process the generator
                # This is important for integrations that wrap the generator
                if (handler := op._on_output_handler) is not None:
                    try:
                        # The handler might return a different generator or wrap the original
                        processed_gen = handler(original_gen, finish, call.inputs)
                        if processed_gen is not original_gen:
                            # The handler returned a different generator, use that
                            # and skip our own accumulation logic
                            # Capture and re-raise any exceptions from the generator
                            try:
                                for value in processed_gen:
                                    yield value
                            except Exception as e:
                                # Make sure to mark the call as finished with the exception
                                if not has_finished:
                                    finish(accumulated_state, e)
                                # Re-raise the exception to preserve user code behavior
                                raise
                            return
                    except Exception as e:
                        # If raise_on_captured_errors is True, propagate the exception
                        if get_raise_on_captured_errors():
                            raise
                        # Otherwise, log the error and continue with the original generator
                        log_once(
                            logger.error, ON_OUTPUT_MSG.format(traceback.format_exc())
                        )

                # If we get here, either there was no handler, it returned the original generator,
                # or it raised an exception that we caught.  Proceed with our normal accumulation logic
                # Capture and re-raise any exceptions from the generator
                try:
                    for value in original_gen:
                        # Ensure call context is set for each yield
                        # This is critical for nested generators
                        current_call = call_context.get_current_call()
                        if current_call is None or current_call.id != call.id:
                            call_context.push_call(call)

                        # Box the value
                        boxed_value = box.box(value)

                        # Accumulate if we have an accumulator
                        if acc:
                            try:
                                accumulated_state = acc(accumulated_state, boxed_value)
                            except StopIteration as e:
                                # Handle special case where accumulator signals end
                                accumulated_state = e.value
                                finish(accumulated_state)
                                return

                        # Update the call's output with the current accumulated state
                        # This ensures the UI shows the actual values, not just a generator object
                        if accumulated_state is not None:
                            call.output = accumulated_state
                        else:
                            call.output = boxed_value

                        # Temporarily pop the call context before yielding
                        # This allows nested generators to establish their own call context
                        current_call = call_context.get_current_call()
                        if current_call and current_call.id == call.id:
                            call_context.pop_call(call.id)

                        # Yield the value to the caller
                        try:
                            yield boxed_value
                        except GeneratorExit:
                            # Generator was closed before exhaustion (e.g., break in for loop)
                            # Ensure we finish the call with the accumulated state so far
                            finish(accumulated_state)
                            return

                        # Re-establish the call context after yielding
                        # This ensures subsequent operations are properly nested
                        call_context.push_call(call)
                except Exception as e:
                    # Make sure to mark the call as finished with the exception
                    if not has_finished:
                        finish(accumulated_state, e)
                    # Re-raise the exception to preserve user code behavior
                    raise

                # Generator completed normally
                finish(accumulated_state)
            except Exception as e:
                # Handle exceptions from the generator
                if not has_finished:
                    finish(accumulated_state, e)
                raise

            finally:
                # Ensure we clean up the call context
                current_call = call_context.get_current_call()
                if current_call and current_call.id == call.id:
                    call_context.pop_call(call.id)

        return wrapped_generator(), call
    except Exception as e:
        # Handle exceptions from initial generator creation
        finish(exception=e)
        if __should_raise:
            raise

        def empty_sync_gen() -> Generator[Any]:
            # Re-raise the original exception if __should_raise is False
            # but we're evaluating the generator, to maintain expected behavior
            if not has_finished:
                nonlocal e
                raise e
            # This will never actually yield anything but is needed for typing
            yield from []

        return empty_sync_gen(), call


async def _call_async_gen(
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    __require_explicit_finish: bool = False,
    **kwargs: Any,
) -> tuple[AsyncIterator, Call]:
    func = op.resolve_fn
    call = placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if should_skip_tracing_for_op(op):
        gen = func(*args, **kwargs)
        call.output = gen
        return gen, call

    if _should_sample_traces(op):
        with tracing_disabled():
            gen = func(*args, **kwargs)
            call.output = gen
            return gen, call

    __weave = setup_dunder_weave_dict(__weave)
    _set_python_function_type_on_weave_dict(__weave, "async_generator")

    # Proceed with tracing
    try:
        call = _create_call(op, *args, __weave=__weave, **kwargs)
    except OpCallError:
        raise
    except Exception:
        if get_raise_on_captured_errors():
            raise
        log_once(
            logger.error,
            ASYNC_CALL_CREATE_MSG.format(traceback.format_exc()),
        )
        gen = func(*args, **kwargs)
        return gen, call

    # Execute the op and get the generator
    client = weave_client_context.require_weave_client()
    has_finished = False
    accumulated_state = None
    acc = op._accumulator

    def finish(output: Any = None, exception: BaseException | None = None) -> None:
        if __require_explicit_finish:
            return

        nonlocal has_finished
        if has_finished:
            return
        has_finished = True

        try:
            # Apply any post-processing to the accumulated state if needed
            try:
                if processor := getattr(op, "_on_finish_post_processor", None):
                    output = processor(output)
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_OUTPUT_MSG.format(traceback.format_exc()))

            client.finish_call(
                call,
                output,
                exception,
                op=op,
            )
        finally:
            # Only pop the call context if we're the current call
            current_call = call_context.get_current_call()
            if current_call and current_call.id == call.id:
                call_context.pop_call(call.id)

    # Create the generator wrapper
    try:
        # Define the wrapper generator that will handle the call context properly
        async def wrapped_generator() -> AsyncIterator:
            nonlocal accumulated_state, has_finished

            # Set the call context before creating the original generator
            # This ensures all calls made during generator initialization are properly nested
            call_context.push_call(call)

            try:
                # Create the original generator within the proper call context
                original_gen = func(*args, **kwargs)

                # If there's an on_output_handler, let it process the generator
                # This is important for integrations that wrap the generator
                if (handler := op._on_output_handler) is not None:
                    try:
                        # The handler might return a different generator or wrap the original
                        processed_gen = handler(original_gen, finish, call.inputs)
                        if processed_gen is not original_gen:
                            # The handler returned a different generator, use that
                            # and skip our own accumulation logic
                            # Capture and re-raise any exceptions from the generator
                            try:
                                async for value in processed_gen:
                                    yield value
                            except Exception as e:
                                # Make sure to mark the call as finished with the exception
                                if not has_finished:
                                    finish(accumulated_state, e)
                                # Re-raise the exception to preserve user code behavior
                                raise
                            return
                    except Exception as e:
                        # If raise_on_captured_errors is True, propagate the exception
                        if get_raise_on_captured_errors():
                            raise
                        # Otherwise, log the error and continue with the original generator
                        log_once(
                            logger.error, ON_OUTPUT_MSG.format(traceback.format_exc())
                        )

                # If we get here, either there was no handler, it returned the original generator,
                # or it raised an exception that we caught.  Proceed with our normal accumulation logic
                # Capture and re-raise any exceptions from the generator
                try:
                    async for value in original_gen:
                        # Ensure call context is set for each yield
                        # This is critical for nested generators
                        current_call = call_context.get_current_call()
                        if current_call is None or current_call.id != call.id:
                            call_context.push_call(call)

                        # Box the value
                        boxed_value = box.box(value)

                        # Accumulate if we have an accumulator
                        if acc:
                            try:
                                accumulated_result = acc(accumulated_state, boxed_value)
                                # If the accumulator is async, await it
                                if inspect.iscoroutine(accumulated_result):
                                    accumulated_state = await accumulated_result
                                else:
                                    accumulated_state = accumulated_result
                            except StopAsyncIteration as e:
                                # Handle special case where accumulator signals end
                                # accumulated_state = e.value
                                finish(accumulated_state)
                                return

                        # Update the call's output with the current accumulated state
                        # This ensures the UI shows the actual values, not just a generator object
                        if accumulated_state is not None:
                            call.output = accumulated_state
                        else:
                            call.output = boxed_value

                        # Temporarily pop the call context before yielding
                        # This allows nested generators to establish their own call context
                        current_call = call_context.get_current_call()
                        if current_call and current_call.id == call.id:
                            call_context.pop_call(call.id)

                        # Yield the value to the caller
                        try:
                            yield boxed_value
                        except GeneratorExit:
                            # Generator was closed before exhaustion (e.g., break in for loop)
                            # Ensure we finish the call with the accumulated state so far
                            finish(accumulated_state)
                            return

                        # Re-establish the call context after yielding
                        # This ensures subsequent operations are properly nested
                        call_context.push_call(call)
                except Exception as e:
                    # Make sure to mark the call as finished with the exception
                    if not has_finished:
                        finish(accumulated_state, e)
                    # Re-raise the exception to preserve user code behavior
                    raise

                # Generator completed normally
                finish(accumulated_state)
            except Exception as e:
                # Handle exceptions from the generator
                if not has_finished:
                    finish(accumulated_state, e)
                raise

            finally:
                # Ensure we clean up the call context
                current_call = call_context.get_current_call()
                if current_call and current_call.id == call.id:
                    call_context.pop_call(call.id)

        return wrapped_generator(), call
    except Exception as e:
        # Handle exceptions from initial generator creation
        finish(exception=e)
        if __should_raise:
            raise

        async def empty_async_gen() -> AsyncIterator[Any]:
            # Re-raise the original exception if __should_raise is False
            # but we're evaluating the generator, to maintain expected behavior
            if not has_finished:
                nonlocal e
                raise e
            # This will never actually yield anything but is needed for typing
            for _ in []:
                yield _

        return empty_async_gen(), call


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
    """Executes the op and returns both the result and a Call representing the execution.

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
    """Get an iterator over all calls to this op.

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


@overload
def op(func: Callable[P, R], **kwargs: Unpack[OpKwargs]) -> Op[P, R]: ...
@overload
def op(**kwargs: Unpack[OpKwargs]) -> Callable[[Callable[P, R]], Op[P, R]]: ...
def op(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    tracing_sample_rate: float = 1.0,
    enable_code_capture: bool = True,
    accumulator: Callable[[Any | None, Any], Any] | None = None,
) -> Callable[[Callable[P, R]], Op[P, R]] | Op[P, R]:
    """A decorator to weave op-ify a function or method. Works for both sync and async.
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
        is_sync_generator = inspect.isgeneratorfunction(func)
        is_async_generator = inspect.isasyncgenfunction(func)

        # Create the appropriate wrapper based on function type
        def create_wrapper(func: Callable[P, R]) -> Op[P, R]:
            if is_async:

                @wraps(func)
                async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportRedeclaration]
                    res, _ = await _call_async_func(
                        cast(Op[P, R], wrapper), *args, __should_raise=True, **kwargs
                    )
                    return cast(R, res)
            elif is_sync_generator:

                @wraps(func)
                def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportRedeclaration]
                    res, _ = _call_sync_gen(
                        cast(Op[P, R], wrapper), *args, __should_raise=True, **kwargs
                    )
                    return cast(R, res)
            elif is_async_generator:

                @wraps(func)
                async def wrapper(  # pyright: ignore[reportRedeclaration]
                    *args: P.args, **kwargs: P.kwargs
                ) -> AsyncGenerator[R]:
                    res, _ = await _call_async_gen(
                        cast(Op[P, R], wrapper), *args, __should_raise=True, **kwargs
                    )
                    async for item in res:
                        yield item
            else:

                @wraps(func)
                def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    res, _ = _call_sync_func(
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
            wrapper._on_finish_post_processor = None  # type: ignore

            wrapper._tracing_enabled = True  # type: ignore
            wrapper.tracing_sample_rate = tracing_sample_rate  # type: ignore

            wrapper._accumulator = accumulator  # type: ignore

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
            wrapper._is_generator = is_sync_generator  # type: ignore
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
        ) from None


def maybe_bind_method(func: Callable, self: Any = None) -> Callable | MethodType:
    """Bind a function to any object (even if it's not a class).

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


def is_op(obj: Any) -> TypeIs[Op]:
    """Check if an object is an Op."""
    if sys.version_info < (3, 12):
        return isinstance(obj, Op)

    return all(hasattr(obj, attr) for attr in Op.__annotations__)


def as_op(fn: Callable[P, R]) -> Op[P, R]:
    """Given a @weave.op decorated function, return its Op.

    @weave.op decorated functions are instances of Op already, so this
    function should be a no-op at runtime. But you can use it to satisfy type checkers
    if you need to access OpDef attributes in a typesafe way.

    Args:
        fn: A weave.op decorated function.

    Returns:
        The Op of the function.
    """
    if not is_op(fn):
        raise ValueError("fn must be a weave.op decorated function")

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
                # Even if an exception occurs, we need to ensure we clean up the call context
                current_call = call_context.get_current_call()
                if current_call is not None:
                    call_context.pop_call(current_call.id)

                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_CLOSE_MSG.format(traceback.format_exc()))
            finally:
                self._on_finished_called = True

    def _call_on_error_once(self, e: Exception) -> None:
        if not self._on_finished_called:
            try:
                self._on_error(e)
            except Exception as e:
                # Even if an exception occurs, we need to ensure we clean up the call context
                current_call = call_context.get_current_call()
                if current_call is not None:
                    call_context.pop_call(current_call.id)

                if get_raise_on_captured_errors():
                    raise
                log_once(logger.error, ON_ERROR_MSG.format(traceback.format_exc()))
            finally:
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
                ) from None
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
                ) from None
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
            raise StopAsyncIteration from e
        except Exception as e:
            self._call_on_error_once(e)
            # Always re-raise user exceptions to maintain the expected behavior
            # This ensures test_resilience_to_accumulator_internal_errors_async passes
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
    value: Iterator[V] | AsyncIterator[V],
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
    @weave.op
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
        value: Iterator[V] | AsyncIterator[V],
        on_finish: FinishCallbackType,
        inputs: dict,
    ) -> Iterator | AsyncIterator:
        if should_accumulate is None or should_accumulate(inputs):
            # we build the accumulator here dependent on the inputs (optional)
            accumulator = make_accumulator(inputs)
            return _build_iterator_from_accumulator_for_op(
                value,
                accumulator,
                on_finish,
                iterator_wrapper,
            )
        else:
            on_finish(value, None)
            return value

    op._set_on_output_handler(on_output)
    op._on_finish_post_processor = on_finish_post_processor
    return op
