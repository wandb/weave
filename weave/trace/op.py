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
from dataclasses import dataclass, fields
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
from weave.trace.context import call_context, weave_client_context
from weave.trace.context.call_context import (
    call_attributes,
    get_tracing_enabled,
    tracing_disabled,
)
from weave.trace.context.tests_context import get_raise_on_captured_errors
from weave.trace.op_accumulator import (
    _add_accumulator as _add_accumulator_impl,
)
from weave.trace.op_accumulator import (
    _build_iterator_from_accumulator_for_op as _build_iterator_from_accumulator_for_op_impl,
)
from weave.trace.op_protocol import (
    CallDisplayNameFunc,
    FinishCallbackType,
    OnFinishHandlerType,
    OnInputHandlerType,
    OnOutputHandlerType,
    Op,
    OpColor,
    Opified,
    OpKind,
    PostprocessInputsFunc,
    PostprocessOutputFunc,
    ProcessedInputs,
)
from weave.trace.util import log_once

if TYPE_CHECKING:
    from weave.trace.call import Call, CallsIter, NoOpCall
    from weave.trace.refs import ObjectRef

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
    kind: OpKind | None
    color: OpColor | None
    eager_call_start: bool

def _unwrap_opified(oplike: Opified[P, R] | MethodType | partial) -> Opified[P, R]:
    if isinstance(oplike, MethodType):
        return cast(Opified[P, R], oplike.__func__)
    if isinstance(oplike, partial):
        return cast(Opified[P, R], oplike.func)
    return oplike


@dataclass
class BaseOp(Generic[P, R]):
    """Nominal runtime sidecar for an inspect-compatible opified callable."""

    op: Opified[P, R] | None = None
    resolve_fn: Callable[P, R] | None = None
    name: str = ""
    ref: ObjectRef | None = None
    call_display_name: str | CallDisplayNameFunc | None = None
    postprocess_inputs: PostprocessInputsFunc | None = None
    postprocess_output: PostprocessOutputFunc | None = None
    _on_input_handler: OnInputHandlerType | None = None
    _on_output_handler: OnOutputHandlerType | None = None
    _on_finish_handler: OnFinishHandlerType | None = None
    _on_finish_post_processor: Callable[[Any], Any] | None = None
    _tracing_enabled: bool = True
    _code_capture_enabled: bool = True
    tracing_sample_rate: float = 1.0
    _accumulator: Callable[[Any | None, Any], Any] | None = None
    kind: OpKind | None = None
    color: OpColor | None = None
    eager_call_start: bool = False

    def __post_init__(self) -> None:
        if self.op is not None:
            self.__op__ = self
            self.__wrapped__ = self.op
            self.__signature__ = inspect.signature(self.op)
            self.__self__ = self

    def __get__(self, instance: object | None, owner: type | None = None) -> Any:
        if instance is None:
            return self
        return BoundOp(MethodType(self.require_opified(), instance))

    def require_opified(self) -> Opified[P, R]:
        if self.op is None:
            raise ValueError("Op sidecar is not attached to an opified callable")
        return self.op

    def require_resolve_fn(self) -> Callable[P, R]:
        if self.resolve_fn is None:
            raise ValueError("Op sidecar is missing resolve_fn")
        return self.resolve_fn

    def sync_from_wrapper(self, op: Opified[P, R]) -> None:
        for attr in _MIRRORED_RUNTIME_OP_ATTRS:
            if hasattr(op, attr):
                setattr(self, attr, getattr(op, attr))

    def mirror_to_wrapper(self, op: Opified[P, R]) -> None:
        for attr in _MIRRORED_RUNTIME_OP_ATTRS:
            setattr(op, attr, getattr(self, attr))

    def call(
        self,
        /,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
        weave_kwargs = cast(WeaveKwargs | None, kwargs.pop("__weave", None))
        should_raise = cast(bool, kwargs.pop("__should_raise", False))
        require_explicit_finish = cast(
            bool, kwargs.pop("__require_explicit_finish", False)
        )
        return call(
            cast(Op, self.require_opified()),
            *args,
            __weave=weave_kwargs,
            __should_raise=should_raise,
            __require_explicit_finish=require_explicit_finish,
            **kwargs,
        )

    def calls(self) -> CallsIter:
        return calls(cast(Op, self.require_opified()))

    def _set_on_input_handler(self, on_input: OnInputHandlerType) -> None:
        _set_on_input_handler(cast(Op, self.require_opified()), on_input)

    def _set_on_output_handler(self, on_output: OnOutputHandlerType) -> None:
        _set_on_output_handler(cast(Op, self.require_opified()), on_output)

    def _set_on_finish_handler(self, on_finish: OnFinishHandlerType) -> None:
        _set_on_finish_handler(cast(Op, self.require_opified()), on_finish)

    def get_captured_code(self) -> str:
        return get_captured_code(cast(Op, self.require_opified()))


# These fields still need wrapper <-> sidecar mirroring because the rest of the
# repo can mutate them directly on the wrapper function for compatibility.
_MIRRORED_RUNTIME_OP_ATTRS = tuple(
    field.name for field in fields(BaseOp) if field.name != "op"
)


def _normalize_sidecar_invoke_target(
    fn: Opified[P, R] | MethodType | partial, args: tuple[Any, ...]
) -> tuple[Opified[P, R], tuple[Any, ...]]:
    normalized_args = args
    if isinstance(fn, MethodType):
        bound_self = fn.__self__
        if bound_self is not None and (not args or args[0] is not bound_self):
            normalized_args = (bound_self, *args)
        normalized_fn = cast(Opified[P, R], fn.__func__)
    elif isinstance(fn, partial):
        normalized_fn = cast(Opified[P, R], fn.func)
        if fn.args:
            normalized_args = (*fn.args, *normalized_args)
        if fn.keywords:
            raise ValueError(
                "Sidecar invocation for partials with keyword arguments is not supported"
            )
    else:
        normalized_fn = fn

    return normalized_fn, normalized_args


@dataclass
class SyncOp(BaseOp[P, R]):
    """Sidecar for sync functions and sync generators."""

    is_generator: bool = False

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.op is None:
            raise ValueError("SyncOp is not attached to an opified callable")
        return self.invoke(self.op, *args, **kwargs)

    def invoke(
        self,
        fn: Opified[P, R] | MethodType | partial,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        fn, args = _normalize_sidecar_invoke_target(fn, args)
        if self.is_generator:
            res, _ = _call_sync_gen(
                cast(Op, fn),
                *args,
                __should_raise=True,
                **kwargs,
            )
        else:
            res, _ = _call_sync_func(
                cast(Op, fn),
                *args,
                __should_raise=True,
                **kwargs,
            )
        return cast(R, res)


@dataclass
class AsyncOp(BaseOp[P, R]):
    """Sidecar for async functions and async generators."""

    is_async_generator: bool = False

    async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        if self.op is None:
            raise ValueError("AsyncOp is not attached to an opified callable")
        return await self.invoke(self.op, *args, **kwargs)

    async def invoke(
        self,
        fn: Opified[P, R] | MethodType | partial,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> R:
        fn, args = _normalize_sidecar_invoke_target(fn, args)
        if self.is_async_generator:
            res, _ = await _call_async_gen(
                cast(Op, fn),
                *args,
                __should_raise=True,
                **kwargs,
            )
        else:
            res, _ = await _call_async_func(
                cast(Op, fn),
                *args,
                __should_raise=True,
                **kwargs,
            )
        return cast(R, res)


def _sync_op_runtime_state(
    oplike: Opified[P, R] | MethodType | partial,
) -> tuple[Opified[P, R], SyncOp[P, R] | AsyncOp[P, R]]:
    # Transitional while wrapper attrs can still diverge from the `__op__` sidecar.
    opified = _unwrap_opified(oplike)
    op_def = get_op_def(opified)
    op_def.sync_from_wrapper(opified)
    return opified, op_def


# Compatibility aliases while the rest of the repo migrates off the old names.
OpDef = SyncOp
AsyncOpDef = AsyncOp


def _set_runtime_attr(
    oplike: Opified[P, R] | MethodType | partial, attr: str, value: Any
) -> None:
    opified = _unwrap_opified(oplike)
    op_def = get_op_def(opified)
    setattr(op_def, attr, value)
    setattr(opified, attr, value)


def _bound_runtime_property(attr: str) -> property:
    def getter(self: BoundOp[Any, Any]) -> Any:
        _, op_def = _sync_op_runtime_state(self._target)
        return getattr(op_def, attr)

    def setter(self: BoundOp[Any, Any], value: Any) -> None:
        _set_runtime_attr(self._target, attr, value)

    return property(getter, setter)


class BoundOp(Generic[P, R]):
    """A bound handle over an opified callable's `__op__` sidecar.

    The wrapper function remains the public inspect-compatible callable.
    `BoundOp` is now reserved for bound callables like methods and partials.
    """

    __op__: SyncOp[P, R] | AsyncOp[P, R]
    __self__: Any
    __wrapped__: Opified[P, R] | MethodType | partial

    def __init__(self, target: Opified[P, R] | MethodType | partial) -> None:
        opified, op_def = _sync_op_runtime_state(target)
        self._target = target
        self._opified = opified
        self.__op__ = op_def
        self.__self__ = getattr(target, "__self__", opified)
        self.__wrapped__ = target
        try:
            self.__signature__ = inspect.signature(target)
        except ValueError:
            self.__signature__ = inspect.signature(opified)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return cast(R, self.__wrapped__(*args, **kwargs))

    resolve_fn = _bound_runtime_property("resolve_fn")
    name = _bound_runtime_property("name")
    ref = _bound_runtime_property("ref")
    call_display_name = _bound_runtime_property("call_display_name")
    postprocess_inputs = _bound_runtime_property("postprocess_inputs")
    postprocess_output = _bound_runtime_property("postprocess_output")
    _on_input_handler = _bound_runtime_property("_on_input_handler")
    _on_output_handler = _bound_runtime_property("_on_output_handler")
    _on_finish_handler = _bound_runtime_property("_on_finish_handler")
    _on_finish_post_processor = _bound_runtime_property("_on_finish_post_processor")
    _tracing_enabled = _bound_runtime_property("_tracing_enabled")
    _code_capture_enabled = _bound_runtime_property("_code_capture_enabled")
    tracing_sample_rate = _bound_runtime_property("tracing_sample_rate")
    _accumulator = _bound_runtime_property("_accumulator")
    kind = _bound_runtime_property("kind")
    color = _bound_runtime_property("color")
    eager_call_start = _bound_runtime_property("eager_call_start")

    def call(
        self,
        /,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, Call] | Coroutine[Any, Any, tuple[Any, Call]]:
        weave_kwargs = cast(WeaveKwargs | None, kwargs.pop("__weave", None))
        should_raise = cast(bool, kwargs.pop("__should_raise", False))
        require_explicit_finish = cast(
            bool, kwargs.pop("__require_explicit_finish", False)
        )
        opified, normalized_args = _normalize_sidecar_invoke_target(self._target, args)
        normalized_kwargs = kwargs
        if isinstance(self._target, MethodType):
            bound_self = self._target.__self__
            if bound_self is not None and kwargs.get("self") is bound_self:
                normalized_kwargs = {k: v for k, v in kwargs.items() if k != "self"}
        return call(
            cast(Op, opified),
            *normalized_args,
            __weave=weave_kwargs,
            __should_raise=should_raise,
            __require_explicit_finish=require_explicit_finish,
            **normalized_kwargs,
        )

    def calls(self) -> CallsIter:
        return calls(cast(Op, self._opified))

    def invoke(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return cast(R, self.__op__.invoke(self._target, *args, **kwargs))

    def _set_on_input_handler(self, on_input: OnInputHandlerType) -> None:
        _set_on_input_handler(cast(Op, self._opified), on_input)

    def _set_on_output_handler(self, on_output: OnOutputHandlerType) -> None:
        _set_on_output_handler(cast(Op, self._opified), on_output)

    def _set_on_finish_handler(self, on_finish: OnFinishHandlerType) -> None:
        _set_on_finish_handler(cast(Op, self._opified), on_finish)

    def get_captured_code(self) -> str:
        return get_captured_code(cast(Op, self._opified))


def setup_dunder_weave_dict(op: Op, d: WeaveKwargs | None = None) -> WeaveKwargs:
    """Sets up a __weave dict used to pass WeaveKwargs to ops.

    Args:
        d: Optional existing WeaveKwargs dict to update.
        op: Op to extract kind and color from.

    Returns:
        WeaveKwargs dict with attributes, display_name, and optionally kind/color set.
    """
    res: dict[str, Any] = {}
    if d is not None:
        res = cast(dict[str, Any], d)
    weave_dict = res.setdefault("attributes", defaultdict(dict)).setdefault("weave", {})
    res.setdefault("display_name", None)

    _, op_def = _sync_op_runtime_state(op)
    if op_def.kind:
        weave_dict["kind"] = op_def.kind
    if op_def.color:
        weave_dict["color"] = op_def.color

    return cast(WeaveKwargs, res)


def _set_on_input_handler(func: Op, on_input: OnInputHandlerType) -> None:
    _, op_def = _sync_op_runtime_state(func)
    if op_def._on_input_handler is not None:
        raise ValueError("Cannot set on_input_handler multiple times")
    _set_runtime_attr(func, "_on_input_handler", on_input)


def _set_on_output_handler(func: Op, on_output: OnOutputHandlerType) -> None:
    _, op_def = _sync_op_runtime_state(func)
    if op_def._on_output_handler is not None:
        raise ValueError("Cannot set on_output_handler multiple times")
    _set_runtime_attr(func, "_on_output_handler", on_output)


def _set_on_finish_handler(func: Op, on_finish: OnFinishHandlerType) -> None:
    _, op_def = _sync_op_runtime_state(func)
    if op_def._on_finish_handler is not None:
        raise ValueError("Cannot set on_finish_handler multiple times")
    _set_runtime_attr(func, "_on_finish_handler", on_finish)


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

    _, op_def = _sync_op_runtime_state(func)
    resolve_fn = op_def.require_resolve_fn()

    try:
        sig = inspect.signature(resolve_fn)
        inputs = sig.bind(*args, **kwargs).arguments
    except TypeError as e:
        raise OpCallError(f"Error calling {op_def.name}: {e}") from e

    inputs_with_defaults = _apply_fn_defaults_to_inputs(resolve_fn, inputs)

    # Annotated input type flow
    # If user defines postprocess_inputs manually, trust it instead of running this
    to_weave_inputs = {}
    if not op_def.postprocess_inputs:
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
    if not op_def.postprocess_output and sig.return_annotation:
        parsed = parse_content_annotation(str(sig.return_annotation))
        if isinstance(parsed, ContentAnnotation):
            _set_runtime_attr(
                func,
                "postprocess_output",
                lambda x: Content._from_guess(
                    x, mimetype=parsed.mimetype, extension=parsed.extension
                ),
            )

    return ProcessedInputs(
        original_args=args,
        original_kwargs=kwargs,
        args=args,
        kwargs=kwargs,
        inputs=to_weave_inputs,
    )


def _create_call(
    func: Op,
    *args: Any,
    __weave: WeaveKwargs | None = None,
    use_stack: bool = True,
    **kwargs: Any,
) -> Call:
    """Create a call object for the given op.

    Args:
        func: The op being called.
        *args: Positional arguments to the op.
        __weave: Optional weave configuration dict.
        use_stack: Whether to push the call onto the call stack. Defaults to True.
            For generators, this should be False since they push when iteration starts.
        **kwargs: Keyword arguments to the op.

    Returns:
        The created Call object.
    """
    client = weave_client_context.require_weave_client()

    _, op_def = _sync_op_runtime_state(func)

    pargs = None
    if op_def._on_input_handler is not None:
        pargs = op_def._on_input_handler(func, args, kwargs)
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
        display_name=call_time_display_name or op_def.call_display_name,
        attributes=attributes,
        use_stack=use_stack,
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
    _, op_def = _sync_op_runtime_state(op)
    return not op_def._tracing_enabled


def _should_sample_traces(op: Op) -> bool:
    if call_context.get_current_call():
        return False  # Don't sample traces for child calls

    _, op_def = _sync_op_runtime_state(op)
    if random.random() > op_def.tracing_sample_rate:
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
    _, op_def = _sync_op_runtime_state(op)
    func = op_def.require_resolve_fn()
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

    __weave = setup_dunder_weave_dict(op, __weave)
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
                if processor := op_def._on_finish_post_processor:
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
        if handler := op_def._on_output_handler:
            return handler(output, finish, call.inputs)

        if (
            op_def._accumulator
            and isinstance(output, (Iterator, Generator, AsyncIterator))
            and not isinstance(output, (str, bytes))
        ):
            return _build_iterator_from_accumulator_for_op(
                output,
                op_def._accumulator,
                finish,
                _IteratorWrapper,
            )

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
    _, op_def = _sync_op_runtime_state(op)
    func = op_def.require_resolve_fn()
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

    __weave = setup_dunder_weave_dict(op, __weave)
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
                if processor := op_def._on_finish_post_processor:
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
        if handler := op_def._on_output_handler:
            return handler(output, finish, call.inputs)

        if (
            op_def._accumulator
            and isinstance(output, AsyncIterator)
            and not isinstance(output, (str, bytes))
        ):
            return _build_iterator_from_accumulator_for_op(
                output,
                op_def._accumulator,
                finish,
                _IteratorWrapper,
            )
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
    _, op_def = _sync_op_runtime_state(op)
    func = op_def.require_resolve_fn()
    call = placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if should_skip_tracing_for_op(op):
        gen = func(*args, **kwargs)
        call.output = gen
        return gen, call

    if _should_sample_traces(op):
        # Generator bodies run at iteration time, so tracing must remain disabled
        # while consuming the iterator (not only while constructing it).
        gen = func(*args, **kwargs)

        def untraced_gen() -> Generator[Any]:
            with tracing_disabled():
                yield from gen

        wrapped_gen = untraced_gen()
        call.output = wrapped_gen
        return wrapped_gen, call

    __weave = setup_dunder_weave_dict(op, __weave)
    _set_python_function_type_on_weave_dict(__weave, "generator")

    # Proceed with tracing
    try:
        # For generators, use_stack=False because we push when iteration starts,
        # not when the call is created. This avoids double-pushing.
        call = _create_call(op, *args, __weave=__weave, use_stack=False, **kwargs)
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
    acc = op_def._accumulator

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
                if processor := op_def._on_finish_post_processor:
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
                if (handler := op_def._on_output_handler) is not None:
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
    _, op_def = _sync_op_runtime_state(op)
    func = op_def.require_resolve_fn()
    call = placeholder_call()

    # Handle all of the possible cases where we would skip tracing.
    if should_skip_tracing_for_op(op):
        gen = func(*args, **kwargs)
        call.output = gen
        return gen, call

    if _should_sample_traces(op):
        # Async generator bodies run at iteration time, so tracing must remain
        # disabled while consuming the async iterator.
        gen = func(*args, **kwargs)

        async def untraced_gen() -> AsyncIterator[Any]:
            with tracing_disabled():
                async for item in gen:
                    yield item

        wrapped_gen = untraced_gen()
        call.output = wrapped_gen
        return wrapped_gen, call

    __weave = setup_dunder_weave_dict(op, __weave)
    _set_python_function_type_on_weave_dict(__weave, "async_generator")

    # Proceed with tracing
    try:
        # For generators, use_stack=False because we push when iteration starts,
        # not when the call is created. This avoids double-pushing.
        call = _create_call(op, *args, __weave=__weave, use_stack=False, **kwargs)
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
    acc = op_def._accumulator

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
                if processor := op_def._on_finish_post_processor:
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
                if (handler := op_def._on_output_handler) is not None:
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
    _, op_def = _sync_op_runtime_state(op)
    if inspect.iscoroutinefunction(op_def.require_resolve_fn()):
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
    kind: OpKind | None = None,
    color: OpColor | None = None,
    eager_call_start: bool = False,
) -> Callable[[Callable[P, R]], Op[P, R]] | Op[P, R]:
    """A decorator to weave op-ify a function or method. Works for both sync and async.
    Automatically detects iterator functions and applies appropriate behavior.

    Args:
        func: The function to decorate.
        name: Custom name for the op. Defaults to the function name.
        call_display_name: Display name for calls, can be a string or callable.
        postprocess_inputs: Function to transform inputs before logging.
        postprocess_output: Function to transform output before logging.
        tracing_sample_rate: Fraction of calls to trace (0.0 to 1.0).
        enable_code_capture: Whether to capture source code for this op.
        accumulator: Function to accumulate results for streaming ops.
        eager_call_start: If True, call starts are sent immediately rather than batched.
            Useful for long-running operations like evaluations that should
            be visible in the UI immediately.
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
                    return cast(
                        R,
                        await cast(AsyncOp[P, R], wrapper.__op__)(*args, **kwargs),
                    )
            elif is_sync_generator:

                @wraps(func)
                def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # pyright: ignore[reportRedeclaration]
                    return cast(
                        R,
                        cast(SyncOp[P, R], wrapper.__op__)(*args, **kwargs),
                    )
            elif is_async_generator:

                @wraps(func)
                async def wrapper(  # pyright: ignore[reportRedeclaration]
                    *args: P.args, **kwargs: P.kwargs
                ) -> AsyncGenerator[R]:
                    res = await cast(AsyncOp[P, R], wrapper.__op__)(*args, **kwargs)
                    async for item in res:
                        yield item
            else:

                @wraps(func)
                def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                    return cast(
                        R,
                        cast(SyncOp[P, R], wrapper.__op__)(*args, **kwargs),
                    )

            # Tack these helpers on to our wrapper
            inferred_name = func.__qualname__ if is_method else func.__name__

            # funcs and methods defined inside another func will have the
            # name prefixed with {outer}.<locals>.{func_name}
            # this is noisy for us, so we strip it out
            inferred_name = inferred_name.split(".<locals>.")[-1]

            op_def: SyncOp[P, R] | AsyncOp[P, R]
            op_def_kwargs = {
                "op": cast(Opified[P, R], wrapper),
                "resolve_fn": func,
                "name": name or inferred_name,
                "ref": None,
                "call_display_name": call_display_name,
                "postprocess_inputs": postprocess_inputs,
                "postprocess_output": postprocess_output,
                "_on_input_handler": None,
                "_on_output_handler": None,
                "_on_finish_handler": None,
                "_on_finish_post_processor": None,
                "_tracing_enabled": True,
                "_code_capture_enabled": enable_code_capture,
                "tracing_sample_rate": tracing_sample_rate,
                "_accumulator": accumulator,
                "kind": kind,
                "color": color,
                "eager_call_start": eager_call_start,
            }
            if is_async or is_async_generator:
                op_def = AsyncOp(
                    is_async_generator=is_async_generator, **op_def_kwargs
                )
            else:
                op_def = SyncOp(is_generator=is_sync_generator, **op_def_kwargs)
            wrapper.__op__ = op_def  # type: ignore
            op_def.mirror_to_wrapper(cast(Opified[P, R], wrapper))

            wrapper.call = partial(call, wrapper)  # type: ignore
            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_input_handler = partial(_set_on_input_handler, wrapper)  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore

            wrapper._set_on_finish_handler = partial(_set_on_finish_handler, wrapper)  # type: ignore

            wrapper.get_captured_code = partial(get_captured_code, wrapper)  # type: ignore

            if callable(call_display_name):
                params = inspect.signature(call_display_name).parameters
                if len(params) != 1:
                    raise DisplayNameFuncError(
                        "`call_display_name` function must take exactly 1 argument (the Call object)"
                    )

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
    if isinstance(oplike, BoundOp):
        op = oplike._opified
    elif isinstance(oplike, (SyncOp, AsyncOp)):
        op = oplike.require_opified()
    elif isinstance(oplike, MethodType):
        op = oplike.__func__
    elif isinstance(oplike, partial):  # Handle cases op is defined as
        op = oplike.func
    else:
        op = oplike

    return cast(Op, op)


def get_op_def(
    oplike: Opified[Any, Any]
    | MethodType
    | partial
    | SyncOp[Any, Any]
    | AsyncOp[Any, Any]
    | BoundOp[Any, Any],
) -> SyncOp | AsyncOp:
    if isinstance(oplike, BoundOp):
        return oplike.__op__
    if isinstance(oplike, (SyncOp, AsyncOp)):
        return oplike

    if isinstance(oplike, MethodType):
        maybe_opified = oplike.__func__
    elif isinstance(oplike, partial):
        maybe_opified = oplike.func
    else:
        maybe_opified = oplike

    op_def = getattr(maybe_opified, "__op__", None)
    if not isinstance(op_def, (SyncOp, AsyncOp)):
        raise TypeError("Expected an opified callable with a __op__ sidecar")
    return op_def


def is_op(obj: Any) -> TypeIs[Op]:
    """Check if an object is an Op."""
    if isinstance(obj, partial):
        return is_op(obj.func)

    sidecar = getattr(obj, "__op__", None)
    if isinstance(sidecar, (SyncOp, AsyncOp)):
        return True

    if sys.version_info < (3, 12):
        return isinstance(obj, Op)

    return all(hasattr(obj, attr) for attr in Op.__annotations__)


def as_op(
    fn: Callable[P, R]
    | MethodType
    | partial
    | SyncOp[P, R]
    | AsyncOp[P, R]
    | BoundOp[P, R],
) -> SyncOp[P, R] | AsyncOp[P, R] | BoundOp[P, R]:
    """Given a @weave.op decorated value, return its nominal op view.

    Plain opified callables return their shared sidecar. Bound methods and
    partials return a `BoundOp` so binding information is preserved.
    """
    if isinstance(fn, BoundOp):
        return fn
    if isinstance(fn, (SyncOp, AsyncOp)):
        return fn
    if isinstance(fn, (MethodType, partial)):
        if not is_op(fn):
            raise ValueError("fn must be a weave.op decorated function")
        return BoundOp(cast(Opified[P, R] | MethodType | partial, fn))
    if not is_op(fn):
        raise ValueError("fn must be a weave.op decorated function")
    return get_op_def(cast(Opified[P, R], fn))


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
            except Exception:
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
        if name in {
            "_iterator_or_ctx_manager",
            "_on_yield",
            "_on_error",
            "_on_close",
            "_on_finished_called",
            "_call_on_error_once",
        }:
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


def _build_iterator_from_accumulator_for_op(
    value: Iterator[V] | AsyncIterator[V],
    accumulator: Callable,
    on_finish: FinishCallbackType,
    iterator_wrapper: type[_IteratorWrapper] = _IteratorWrapper,
) -> _IteratorWrapper:
    return _build_iterator_from_accumulator_for_op_impl(
        value,
        accumulator,
        on_finish,
        iterator_wrapper,
    )


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
    return _add_accumulator_impl(
        op,
        make_accumulator,
        should_accumulate=should_accumulate,
        on_finish_post_processor=on_finish_post_processor,
        iterator_wrapper=iterator_wrapper,
    )
