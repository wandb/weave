"""Defines the Op protocol and related functions."""

from __future__ import annotations

import inspect
import logging
import sys
import traceback
from collections.abc import Coroutine, Mapping
from contextlib import contextmanager
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
)

from weave.trace import box, settings
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.context import call_context
from weave.trace.context import weave_client_context as weave_client_context
from weave.trace.context.call_context import call_attributes
from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.errors import OpCallError
from weave.trace.op_lifecycle import (
    Callback,
    LifecycleHandler,
    Reducer,
    ReducerCallback,
)
from weave.trace.refs import ObjectRef
from weave.trace.util import log_once

logger = logging.getLogger(__name__)

WEAVE_KWARGS_KEY = "__weave"

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
                inputs[param_name] = ()
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                inputs[param_name] = {}
    return inputs


class WeaveKwargs(TypedDict):
    display_name: str | None


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

    lifecycle_handler: LifecycleHandler

    _set_on_input_handler: Callable[[OnInputHandlerType], None]
    _on_input_handler: OnInputHandlerType | None

    # not sure if this is the best place for this, but kept for compat
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: OnOutputHandlerType | None

    _set_on_finish_handler: Callable[[OnFinishHandlerType], None]
    _on_finish_handler: OnFinishHandlerType | None

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

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        # Very important for `call_time_display_name` to take precedence over `func.call_display_name`
        display_name=call_time_display_name or func.call_display_name,
        attributes=attributes,
    )


def _execute_op(
    __op: Op,
    __call: Call,
    *args: Any,
    __should_raise: bool = True,
    **kwargs: Any,
) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
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
        if not call_context.get_current_call():
            print_call_link(__call)

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

    if settings.should_disable_weave():
        res = func(*pargs.args, **pargs.kwargs)
    elif weave_client_context.get_weave_client() is None:
        res = func(*pargs.args, **pargs.kwargs)
    elif not op._tracing_enabled:
        res = func(*pargs.args, **pargs.kwargs)
    else:
        try:
            # This try/except allows us to fail gracefully and
            # still let the user code continue to execute
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
    op: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    __should_raise: bool = False,
    **kwargs: Any,
) -> tuple[Any, Call]:
    func = op.resolve_fn
    call = _placeholder_call()
    if settings.should_disable_weave():
        res = await func(*args, **kwargs)
    elif weave_client_context.get_weave_client() is None:
        res = await func(*args, **kwargs)
    elif not op._tracing_enabled:
        res = await func(*args, **kwargs)
    else:
        try:
            # This try/except allows us to fail gracefully and
            # still let the user code continue to execute
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
            execute_result = cast(
                Coroutine[Any, Any, tuple[Any, "Call"]], execute_result
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
    callbacks: list[Callback] | None = None,
    reducers: list[Reducer] | None = None,
) -> Op: ...


@overload
def op(
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    callbacks: list[Callback] | None = None,
    reducers: list[Reducer] | None = None,
) -> Callable[[Callable], Op]: ...


def op(
    func: Callable | None = None,
    *,
    name: str | None = None,
    call_display_name: str | CallDisplayNameFunc | None = None,
    postprocess_inputs: PostprocessInputsFunc | None = None,
    postprocess_output: PostprocessOutputFunc | None = None,
    callbacks: list[Callback] | None = None,
    reducers: list[Reducer] | None = None,
    # == Below are escape hatches for integrations -- not for general use ==
    # Force op execution down the accumulator path.  This is useful when the decorated
    # function does not otherwise pass the internal should_accumulate check.
    __should_accumulate: Callable[[Call], bool] | None = None,
    # If the op returns an iterator-like object but it doesn't match the basic iterator
    # protocol, you can use this to convert it into an iterator that does.
    __custom_iterator_wrapper: Callable[[Op, Any, Any, Call, bool], Any] | None = None,
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
        is_method = _is_unbound_method(func)
        is_async = inspect.iscoroutinefunction(func)
        is_async_iterable = _is_async_iterable(func)

        def create_wrapper(func: Callable) -> Op:
            if is_async:

                @wraps(func)
                async def wrapper(*args: Any, **kwargs: Any) -> Any:  # pyright: ignore[reportRedeclaration]
                    res, _ = await _exc_op_async(
                        cast(Op, wrapper),
                        args,
                        kwargs,
                        should_accumulate=__should_accumulate,
                    )
                    return res
            elif is_async_iterable:

                @wraps(func)
                async def wrapper(*args: Any, **kwargs: Any) -> Any:  # pyright: ignore[reportRedeclaration]
                    res, _ = await _exc_op_async(
                        cast(Op, wrapper),
                        args,
                        kwargs,
                        should_accumulate=__should_accumulate,
                    )
                    # We must explicitly write this to force python to recognize
                    # that the wrapper is an async generator
                    async for v in res:
                        yield v
            else:

                @wraps(func)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    res, _ = _exc_op(
                        cast(Op, wrapper),
                        args,
                        kwargs,
                        should_accumulate=__should_accumulate,
                        custom_iterator_wrapper=__custom_iterator_wrapper,
                    )
                    return res

            # Tack these helpers on to our wrapper
            wrapper.resolve_fn = func  # type: ignore

            inferred_name = func.__qualname__ if is_method else func.__name__

            # funcs and methods defined inside another func will have the
            # name prefixed with {outer}.<locals>.{func_name}
            # this is noisy for us, so we strip it out
            inferred_name = inferred_name.split(".<locals>.")[-1]

            wrapper.name = name or inferred_name  # type: ignore
            wrapper.ref = None  # type: ignore

            nonlocal reducers
            nonlocal callbacks
            reducers = reducers or []
            if inspect.isgeneratorfunction(func) and not reducers:
                reducers.append(_default_list_reducer)

            callbacks = callbacks or []
            callbacks += [ReducerCallback(reducer) for reducer in reducers]
            wrapper.lifecycle_handler = LifecycleHandler(callbacks)

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

    return cast(Op, fn)


class SyncIterableContext:
    """Wraps an op that returns an iterable contextmanager to add relevant lifecycle hooks.

    This is used for streaming ops, where we want to accumulate the output of the op until
    the context manager is closed.  This is currently only used for Anthropic streaming ops.
    """

    def __init__(self, op: Op, args: Any, kwargs: Any, call: Call, should_raise: bool):
        self.op = op
        self.args = args
        self.kwargs = kwargs
        self.call = call
        self.should_raise = should_raise
        self.orig_contextmanager = op.resolve_fn(*args, **kwargs)

        # If the context manager is also iterable...
        self._context_value = None
        self._iterator = None

    def __iter__(self):
        return self

    def __next__(self):
        if self._iterator is None:
            raise TypeError("Context value is not iterable")
        try:
            val = next(self._iterator)
        except StopIteration:
            raise
        self.op.lifecycle_handler.before_yield(self.call, val)
        return val

    def __enter__(self):
        self._context_value = self.orig_contextmanager.__enter__()
        if hasattr(self._context_value, "__iter__"):
            self._iterator = iter(self._context_value)
            return self
        return self._context_value

    def __exit__(self, exc_type, exc_value, traceback):
        if self.op.lifecycle_handler.has_finished:
            raise OpCallError("Should not call finish more than once")

        boxed_output = box.box(self.call.output)
        client = weave_client_context.require_weave_client()
        client.finish_call(self.call, boxed_output, exc_value, op=self.op)
        # self.op.lifecycle_handler.has_finished = True

        if not call_context.get_current_call():
            print_call_link(self.call)
        call_context.pop_call(self.call.id)

        return self.orig_contextmanager.__exit__(exc_type, exc_value, traceback)


class AsyncIterableContext:
    """Wraps an op that returns an async iterable contextmanager to add relevant lifecycle hooks.

    This is used for streaming ops, where we want to accumulate the output of the op until
    the context manager is closed.  This is currently only used for Anthropic streaming ops.
    """

    def __init__(self, op: Op, args: Any, kwargs: Any, call: Call, should_raise: bool):
        self.op = op
        self.args = args
        self.kwargs = kwargs
        self.call = call
        self.should_raise = should_raise
        self.orig_contextmanager = op.resolve_fn(*args, **kwargs)

        # If the context manager is also iterable...
        self._context_value = None
        self._aiterator = None

    async def __aenter__(self):
        self._context_value = await self.orig_contextmanager.__aenter__()
        if hasattr(self._context_value, "__aiter__"):
            self._aiterator = self._context_value.__aiter__()
            return self
        return self._context_value

    async def __aexit__(self, exc_type, exc_value, traceback):
        if self.op.lifecycle_handler.has_finished:
            raise OpCallError("Should not call finish more than once")

        boxed_output = box.box(self.call.output)
        client = weave_client_context.require_weave_client()
        client.finish_call(self.call, boxed_output, exc_value, op=self.op)
        # self.op.lifecycle_handler.has_finished = True

        if not call_context.get_current_call():
            print_call_link(self.call)
        call_context.pop_call(self.call.id)

        return await self.orig_contextmanager.__aexit__(exc_type, exc_value, traceback)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._aiterator is None:
            raise TypeError("Context value is not async iterable")
        try:
            val = await self._aiterator.__anext__()
        except StopAsyncIteration:
            raise
        self.op.lifecycle_handler.before_yield(self.call, val)
        return val


@contextmanager
def _call_context(op: Op, call: Call, should_raise: bool):
    """Contextmanager to safely handle errors and finish op calls.

    This is used to wrap the execution of an op, and is used to handle errors and finish
    the call.
    """
    try:
        yield
    except Exception as e:
        exception = e
        op.lifecycle_handler.after_error(call, exception)
        if should_raise:
            raise
    else:
        exception = None
    finally:
        if op.lifecycle_handler.has_finished:
            raise OpCallError("Should not call finish more than once")
        boxed_output = box.box(call.output)
        op.lifecycle_handler.before_call_finish(call)
        client = weave_client_context.require_weave_client()
        client.finish_call(call, boxed_output, exception, op=op)

        if not call_context.get_current_call():
            print_call_link(call)

        call_context.pop_call(call.id)


async def _exc_op_async(
    op: Op,
    args: Any,
    kwargs: Any,
    weave: WeaveKwargs | None = None,
    should_raise: bool = True,
    should_accumulate: Callable[[Call], bool] | None = None,
    custom_iterator_wrapper: Callable[[Any], Any] | None = None,
) -> tuple[Any, Call]:
    func = op.resolve_fn
    call = _placeholder_call()

    # Early returns for disabled cases -- no call is created
    if settings.should_disable_weave():
        return await func(*args, **kwargs), call
    elif not weave_client_context.get_weave_client():
        return await func(*args, **kwargs), call
    elif not op._tracing_enabled:
        return await func(*args, **kwargs), call

    # Setup call context
    client = weave_client_context.require_weave_client()
    parent_call = call_context.get_current_call()
    attributes = call_attributes.get()

    # Create the call
    call_time_display_name = weave.get("display_name") if weave else None
    inputs = inspect.signature(func).bind(*args, **kwargs).arguments
    op.lifecycle_handler.before_call_start(inputs, parent_call, attributes)
    call = client.create_call(
        op,
        inputs,
        parent_call,
        attributes,
        display_name=call_time_display_name or op.call_display_name,
    )

    is_async_iterable = _is_async_iterable(func)
    _should_accumulate = should_accumulate and should_accumulate(call)
    if is_async_iterable or _should_accumulate:
        if custom_iterator_wrapper:
            res = await custom_iterator_wrapper(op, args, kwargs, call, should_raise)
        else:

            @wraps(func)
            async def _wrapped_async_generator() -> Any:
                with _call_context(op, call, should_raise):
                    async for val in await func(*args, **kwargs):
                        op.lifecycle_handler.before_yield(call, val)
                        yield val

            res = await _wrapped_async_generator()
    else:
        # regular async func
        with _call_context(op, call, should_raise):
            res = await func(*args, **kwargs)
            call.output = res

    return res, call


def _exc_op(
    op: Op,
    args: Any,
    kwargs: Any,
    weave: WeaveKwargs | None = None,
    should_raise: bool = True,
    should_accumulate: Callable[[Call], bool] | None = None,
    custom_iterator_wrapper: Callable[[Any], Any] | None = None,
) -> tuple[Any, Call]:
    """Executes an op and calls with its relevant lifecycle hooks."""
    func = op.resolve_fn
    call = _placeholder_call()

    # Early returns for disabled cases -- no call is created
    if settings.should_disable_weave():
        return func(*args, **kwargs), call
    elif not weave_client_context.get_weave_client():
        return func(*args, **kwargs), call
    elif not op._tracing_enabled:
        return func(*args, **kwargs), call

    # Setup call context
    client = weave_client_context.require_weave_client()
    parent_call = call_context.get_current_call()
    attributes = call_attributes.get()

    # Create the call
    call_time_display_name = weave.get("display_name") if weave else None
    inputs = inspect.signature(func).bind(*args, **kwargs).arguments
    op.lifecycle_handler.before_call_start(inputs, parent_call, attributes)
    call = client.create_call(
        op,
        inputs,
        parent_call,
        attributes,
        display_name=call_time_display_name or op.call_display_name,
    )

    is_generator = inspect.isgeneratorfunction(func)
    _should_accumulate = should_accumulate and should_accumulate(call)
    if is_generator or _should_accumulate:
        if custom_iterator_wrapper:
            res = custom_iterator_wrapper(op, args, kwargs, call, should_raise)
        else:

            @wraps(func)
            def _wrapped_sync_generator() -> Any:
                with _call_context(op, call, should_raise):
                    for val in func(*args, **kwargs):
                        op.lifecycle_handler.before_yield(call, val)
                        yield val

            res = _wrapped_sync_generator()
    else:
        # regular sync func
        with _call_context(op, call, should_raise):
            res = func(*args, **kwargs)
            call.output = res
    return res, call


def _is_async_iterable(obj: Any) -> bool:
    """Check if an object is async iterable.

    This is more lenient than `inspect.isasyncgenfunction`, which only returns True if
    the object is literally defined as an async generator function and not just implements
    the async iterator protocol.
    """
    return hasattr(obj, "__aiter__") and hasattr(obj, "__anext__")


def _default_list_reducer(val: Any, acc: list[Any] | None = None) -> list[Any]:
    if acc is None:
        acc = []

    return acc + [val]


__docspec__ = [call, calls]
