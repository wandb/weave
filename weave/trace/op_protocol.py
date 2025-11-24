from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Protocol,
    overload,
    runtime_checkable,
)

from typing_extensions import ParamSpec, TypeVar

if TYPE_CHECKING:
    from weave.trace.call import Call, CallsIter
    from weave.trace.refs import ObjectRef

P = ParamSpec("P")
R = TypeVar("R")


@runtime_checkable
class Op(Protocol[P, R]):
    """The interface for Op-ified functions and methods.

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

    _accumulator: Callable[[Any | None, Any], Any] | None

    _set_on_input_handler: Callable[[OnInputHandlerType], None]
    _on_input_handler: OnInputHandlerType | None

    # not sure if this is the best place for this, but kept for compat
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: OnOutputHandlerType | None

    _set_on_finish_handler: Callable[[OnFinishHandlerType], None]
    _on_finish_handler: OnFinishHandlerType | None
    _on_finish_post_processor: Callable[[Any], Any] | None

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


OnInputHandlerType = Callable[["Op", tuple, dict], ProcessedInputs | None]
FinishCallbackType = Callable[[Any, BaseException | None], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, dict], Any]
OnFinishHandlerType = Callable[["Call", Any, BaseException | None], None]
CallDisplayNameFunc = Callable[["Call"], str]
PostprocessInputsFunc = Callable[[dict[str, Any]], dict[str, Any]]
PostprocessOutputFunc = Callable[..., Any]
