import inspect
import json
import logging
import types
from typing import Any, Optional, Union

from pydantic import BaseModel

from weave.integrations.patcher import Patcher
from weave.trace.context import weave_client_context
from weave.trace.util import log_once
from weave.trace.weave_client import Call, WeaveClient

_import_failed = False

try:
    from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
    from llama_index.core.instrumentation.events.base import BaseEvent
    from llama_index.core.instrumentation.span_handlers.base import BaseSpanHandler
    from llama_index.core.workflow.errors import WorkflowDone
    from llama_index.core.workflow.events import StopEvent
except ImportError:
    _import_failed = True
except Exception:
    _import_failed = True

# Module-level shared state
_weave_calls_map: dict[Union[str, tuple[Optional[str], str]], Call] = {}
_weave_client_instance: Optional[WeaveClient] = None
_accumulators: dict[str, list[Any]] = {}

logger = logging.getLogger(__name__)


def get_weave_client() -> Optional[WeaveClient]:
    """Get the weave client, returning None if weave hasn't been initialized."""
    global _weave_client_instance
    if _weave_client_instance is None:
        try:
            _weave_client_instance = weave_client_context.require_weave_client()
        except Exception:
            # weave.init() hasn't been called
            return None
    return _weave_client_instance


def _convert_instance_to_dict(obj: Any) -> Any:
    """Convert a class instance to a dict if possible."""
    if isinstance(obj, BaseModel):  # Handle pydantic models
        return obj.model_dump(exclude_none=True)
    elif hasattr(obj, "__dict__"):  # Handle regular class instances
        return {
            k: v
            for k, v in vars(obj).items()
            if not k.startswith("__") and not callable(v)
        }
    return obj


def _get_class_name(obj: Any) -> str:
    """Get a meaningful class name from an object."""
    # Try class_name() method first (common in LlamaIndex)
    if hasattr(obj, "class_name") and callable(obj.class_name):
        result = obj.class_name()
        return str(result) if result is not None else obj.__class__.__name__
    # Try class name from the class itself
    return str(obj.__class__.__name__)


def _process_inputs(raw_inputs: dict[str, Any]) -> dict[str, Any]:
    """Process inputs to ensure JSON serializability and handle special cases."""
    processed: dict[str, Any] = {}

    for k, v in raw_inputs.items():
        # Handle lists of instances
        if isinstance(v, (list, tuple)) and len(v) > 0:
            # Check if list contains class instances
            first_item = v[0]
            if hasattr(first_item, "__class__") and not isinstance(
                first_item, (str, int, float, bool, dict, list, tuple)
            ):
                # Convert list of instances to dict with class names as keys
                processed[k] = {
                    f"{_get_class_name(item)}_{i}": _convert_instance_to_dict(item)
                    for i, item in enumerate(v)
                }
                continue

        # Handle single instances
        if hasattr(v, "__class__") and not isinstance(
            v, (str, int, float, bool, dict, list, tuple)
        ):
            processed[k] = _convert_instance_to_dict(v)
            continue

        # Ensure JSON serializability for other types
        try:
            json.dumps(v)
            processed[k] = v
        except (TypeError, OverflowError):
            processed[k] = str(v)

        if k == "_self":
            processed["self"] = v
            processed.pop(k)

    return processed


def _get_op_name_from_span(span_id: str) -> str:
    """Get operation name from span ID."""
    op_name_base = span_id.split("-")[0] if "-" in span_id else span_id
    return f"llama_index.span.{op_name_base}"


if not _import_failed:

    class WeaveSpanHandler(BaseSpanHandler[Any]):  # pyright: ignore[reportRedeclaration]
        """Handles LlamaIndex span start, end, and drop events to trace operations."""

        @classmethod
        def class_name(cls) -> str:
            return "WeaveSpanHandler"

        def _map_args_to_params(
            self,
            instance: Any,
            bound_args: Any,
            id_: str,
        ) -> dict[str, Any]:
            """Maps arguments to their parameter names using Python's introspection."""
            inputs = {}

            # First add any relevant instance variables if this is a method call
            if instance is not None:
                try:
                    instance_vars = {
                        k: v
                        for k, v in vars(instance).items()
                        if not k.startswith("__")
                        and not callable(v)
                        and not isinstance(v, (types.ModuleType, types.FunctionType))
                    }
                    inputs.update(instance_vars)
                except (TypeError, AttributeError):
                    pass

            # Then add the actual function arguments
            if bound_args is not None:
                # Get the function name from the span ID
                func_name = id_.split(".")[-1].split("-")[0] if "." in id_ else None

                try:
                    # Get the raw args and kwargs
                    args = getattr(bound_args, "args", ())
                    kwargs = getattr(bound_args, "kwargs", {})

                    if func_name and instance is not None:
                        # Try to get the method from the instance
                        method = getattr(instance, func_name, None)
                        if method is not None:
                            # If it's a bound method, get its original function
                            if hasattr(method, "__func__"):
                                method = method.__func__

                            # Get the signature
                            sig = inspect.signature(method)

                            # Instead of trying to bind, we'll match parameters manually
                            param_names = list(sig.parameters.keys())

                            # Map positional args to their parameter names
                            for i, arg in enumerate(args):
                                if i < len(param_names):
                                    inputs[param_names[i]] = arg

                            # Add any kwargs that match parameter names
                            for param_name in param_names:
                                if param_name in kwargs:
                                    inputs[param_name] = kwargs[param_name]
                except Exception:
                    pass

            return inputs

        def new_span(
            self,
            id_: str,
            bound_args: Any,
            instance: Optional[Any] = None,
            parent_span_id: Optional[str] = None,
            tags: Optional[dict[str, Any]] = None,
            **kwargs: Any,
        ) -> None:
            """Creates a Weave call when a LlamaIndex span starts."""
            gc = get_weave_client()
            if gc is None:
                log_once(
                    logger.warn,
                    "Please call `weave.init()` to enable LlamaIndex tracing",
                )
                return
            op_name = _get_op_name_from_span(id_)

            # Map arguments to their parameter names
            raw_combined_inputs = self._map_args_to_params(instance, bound_args, id_)

            # Process the inputs - just ensure JSON serializability
            inputs = _process_inputs(raw_combined_inputs)

            # Add any tags if present
            if tags:
                inputs["_tags"] = tags

            parent_call = None
            if parent_span_id and parent_span_id in _weave_calls_map:
                parent_call = _weave_calls_map[parent_span_id]

            # we check if the span is streaming by checking if the op_name contains streaming indicators
            self._is_streaming = (
                op_name.endswith("stream_complete")
                or op_name.endswith("astream_complete")
                or op_name.endswith("stream_chat")
                or op_name.endswith("astream_chat")
            )

            try:
                call = gc.create_call(op_name, inputs, parent_call)
                _weave_calls_map[id_] = call  # Store by full span ID
                # we store the spans that are streaming in nature as a dict of id_ to call
                if self._is_streaming:
                    _accumulators[id_] = [call, False, {}, None, None]
            except Exception as e:
                log_once(
                    logger.error, f"Error creating call for {op_name} (ID: {id_}): {e}"
                )

        def _prepare_to_exit_or_drop(
            self,
            id_: str,
            result: Optional[Any] = None,
            err: Optional[BaseException] = None,
        ) -> None:
            """Common logic for finishing a Weave call for a LlamaIndex span."""
            gc = get_weave_client()
            if gc is None:
                return

            # For streaming spans, defer finishing until EndEvent to keep span on call stack
            # for proper OpenAI autopatch parenting
            if id_ in _accumulators:
                acc_entry = _accumulators[id_]
                # Store result/error for later use, but keep span call active
                acc_entry[3] = result
                acc_entry[4] = err
                _accumulators[id_] = acc_entry
                return

            # Non-streaming spans: finish immediately
            if id_ in _weave_calls_map:
                call_to_finish = _weave_calls_map.pop(id_)
                outputs = None
                exception_to_log = err

                # WorkflowDone is not an error, it's the normal way workflows signal completion
                if (
                    err is not None
                    and not _import_failed
                    and isinstance(err, WorkflowDone)
                ):
                    exception_to_log = None

                if result is not None and isinstance(result, StopEvent):
                    result = result.result

                if result is not None:
                    try:
                        if isinstance(result, BaseModel):
                            outputs = _process_inputs(
                                result.model_dump(exclude_none=True)
                            )
                        else:
                            outputs = _process_inputs({"result": result})
                    except Exception:
                        outputs = _process_inputs({"result": str(result)})

                try:
                    gc.finish_call(call_to_finish, outputs, exception=exception_to_log)
                except Exception as e:
                    error_type = "dropping" if err else "finishing"
                    log_once(logger.error, f"Error {error_type} call for ID {id_}: {e}")

        def prepare_to_exit_span(
            self,
            id_: str,
            bound_args: Any,
            instance: Optional[Any] = None,
            result: Optional[Any] = None,
            **kwargs: Any,
        ) -> Any:
            """Finishes the Weave call when a LlamaIndex span exits successfully."""
            self._prepare_to_exit_or_drop(id_, result=result)
            return result

        def prepare_to_drop_span(
            self,
            id_: str,
            bound_args: Any,
            instance: Optional[Any] = None,
            err: Optional[BaseException] = None,
            **kwargs: Any,
        ) -> Any:
            """Finishes the Weave call with an error when a LlamaIndex span is dropped."""
            self._prepare_to_exit_or_drop(id_, err=err)
            return None

    class WeaveEventHandler(BaseEventHandler):  # pyright: ignore[reportRedeclaration]
        """Handles LlamaIndex events to create fine-grained Weave calls within spans."""

        @classmethod
        def class_name(cls) -> str:
            return "WeaveEventHandler"

        def _get_base_event_name(self, event_class_name: str) -> str:
            """Get the base event name without Start/End suffix."""
            for suffix in ["StartEvent", "EndEvent", "Event"]:
                if event_class_name.endswith(suffix):
                    return event_class_name[: -len(suffix)]
            return event_class_name

        def handle(self, event: BaseEvent) -> None:
            """Processes a LlamaIndex event, creating or finishing a Weave call."""
            gc = get_weave_client()
            if gc is None:
                log_once(
                    logger.warn,
                    "Please call `weave.init()` to enable LlamaIndex tracing",
                )
                return
            event_class_name = event.class_name()

            # Get base event name (e.g., "Embedding" from "EmbeddingStartEvent")
            base_event_name = self._get_base_event_name(event_class_name)
            op_name = f"llama_index.event.{base_event_name}"

            is_start_event = event_class_name.endswith("StartEvent")
            is_end_event = event_class_name.endswith("EndEvent")
            is_progress_event = event_class_name.endswith("InProgressEvent")

            # Key for pairing start and end events.
            event_pairing_key: tuple[Optional[str], str] = (event.span_id, op_name)

            try:
                raw_event_payload = event.model_dump(exclude_none=True)
            except Exception:
                raw_event_payload = {"detail": str(event)}

            try:
                if is_start_event:
                    # Parent: span call or global root
                    parent_call_for_event = _weave_calls_map.get(event.span_id)
                    # Create a new call for the start event
                    call = gc.create_call(
                        op_name, raw_event_payload, parent_call_for_event
                    )
                    _weave_calls_map[event_pairing_key] = call

                    # For streaming LLMCompletion and LLMChat events, pre-create the InProgress call
                    # so that OpenAI autopatch inherits it as parent
                    if (
                        base_event_name in ["LLMCompletion", "LLMChat"]
                    ) and event.span_id in _accumulators:
                        progress_op_name = (
                            f"llama_index.event.{base_event_name}InProgress"
                        )
                        progress_event_key = (event.span_id, progress_op_name)
                        # Create InProgress call as child of LLM start event
                        progress_call = gc.create_call(
                            progress_op_name, raw_event_payload, call
                        )
                        _weave_calls_map[progress_event_key] = progress_call
                        # Update accumulator to point to the pre-created progress call
                        acc_entry = _accumulators[event.span_id]
                        _accumulators[event.span_id] = [
                            progress_call,
                            True,
                            raw_event_payload,
                            acc_entry[3],
                            acc_entry[4],
                        ]
                elif is_progress_event:
                    # Get or create accumulator entry
                    if event.span_id not in _accumulators:
                        _accumulators[event.span_id] = [None, False, {}, None, None]

                    acc_entry = _accumulators[event.span_id]
                    acc_entry[2] = raw_event_payload
                elif is_end_event:
                    # Parent: span call or global root
                    parent_call_for_event = _weave_calls_map.get(event.span_id)
                    # Try to close the call for the progress event first
                    deferred_result = None
                    deferred_err = None
                    if event.span_id in _accumulators:
                        acc_entry = _accumulators.pop(event.span_id)
                        progress_call, _, last_progress_payload = (
                            acc_entry[0],
                            acc_entry[1],
                            acc_entry[2],
                        )
                        # Capture deferred values from the popped accumulator entry
                        if len(acc_entry) >= 5:
                            deferred_result = acc_entry[3]
                            deferred_err = acc_entry[4]

                        if (
                            progress_call is not None
                            and last_progress_payload is not None
                        ):
                            gc.finish_call(progress_call, last_progress_payload)
                    if event_pairing_key in _weave_calls_map:
                        # Found matching start event, finish its call with end event data
                        call_to_finish = _weave_calls_map.pop(event_pairing_key)
                        gc.finish_call(call_to_finish, raw_event_payload)
                    else:
                        # No matching start event found, create a standalone call
                        call = gc.create_call(
                            op_name, raw_event_payload, parent_call_for_event
                        )
                        gc.finish_call(call, raw_event_payload)

                    # Only finish spans that were deferred due to streaming (indicated by deferred_result or deferred_err being set)
                    if event.span_id in _weave_calls_map and (
                        deferred_result is not None or deferred_err is not None
                    ):
                        span_call = _weave_calls_map.pop(event.span_id)

                        outputs = None
                        if deferred_result is not None:
                            try:
                                if isinstance(deferred_result, BaseModel):
                                    outputs = _process_inputs(
                                        deferred_result.model_dump(exclude_none=True)
                                    )
                                else:
                                    outputs = _process_inputs(
                                        {"result": deferred_result}
                                    )
                            except Exception:
                                outputs = _process_inputs(
                                    {"result": str(deferred_result)}
                                )

                        gc.finish_call(span_call, outputs, exception=deferred_err)
                    else:
                        pass
                else:
                    # Parent: span call or global root
                    parent_call_for_event = _weave_calls_map.get(event.span_id)
                    # Handle non-start/end events as instantaneous events
                    call = gc.create_call(
                        op_name, raw_event_payload, parent_call_for_event
                    )
                    gc.finish_call(call, raw_event_payload)
            except Exception as e:
                print(
                    f"Weave(EventHandler): Error processing event {op_name} (Key: {event_pairing_key}): {e}"
                )

else:

    class WeaveSpanHandler:  # type: ignore
        pass

    class WeaveEventHandler:  # type: ignore
        pass


class LLamaIndexPatcher(Patcher):  # pyright: ignore[reportRedeclaration]
    """Manages patching of LlamaIndex instrumentation to integrate with Weave."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: Optional[Any] = None
        self._original_event_handlers: Optional[list[BaseEventHandler]] = None
        self._original_span_handlers: Optional[list[BaseSpanHandler[Any]]] = None
        self.weave_event_handler: Optional[WeaveEventHandler] = None
        self.weave_span_handler: Optional[WeaveSpanHandler] = None

    def attempt_patch(self) -> bool:
        """Attempts to patch LlamaIndex instrumentation and set up Weave handlers."""
        global _import_failed
        if _import_failed:
            return False

        try:
            import llama_index.core.instrumentation as instrument

            self.dispatcher = instrument.get_dispatcher()
            self._original_event_handlers = list(self.dispatcher.event_handlers)
            self._original_span_handlers = list(self.dispatcher.span_handlers)

            self.weave_event_handler = WeaveEventHandler()
            self.weave_span_handler = WeaveSpanHandler()

            self.dispatcher.add_event_handler(self.weave_event_handler)
            self.dispatcher.add_span_handler(self.weave_span_handler)

        except Exception as e:
            log_once(logger.error, f"Failed to patch LlamaIndex dispatcher: {e}")
            return False
        return True

    def undo_patch(self) -> bool:
        """Reverts LlamaIndex instrumentation to its original state."""
        if (
            not self.dispatcher
            or self._original_event_handlers is None
            or self._original_span_handlers is None
        ):
            return False

        try:
            self.dispatcher.event_handlers = self._original_event_handlers
            self.dispatcher.span_handlers = self._original_span_handlers

            self._original_event_handlers = None
            self._original_span_handlers = None
            self.weave_event_handler = None
            self.weave_span_handler = None
            self.dispatcher = None
        except Exception as e:
            log_once(logger.error, f"Failed to undo LlamaIndex dispatcher patch: {e}")
            return False
        return True


llamaindex_patcher = LLamaIndexPatcher()
