import atexit  # Added for cleanup
import json
from typing import Any, Dict, List, Optional, Tuple, Union
import inspect
import types

from weave.integrations.patcher import Patcher
from weave.trace.context import weave_client_context
from weave.trace.weave_client import Call, WeaveClient

_import_failed = False

try:
    from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler

    from llama_index.core.instrumentation.events.agent import (
        AgentToolCallEvent,
    )
    from llama_index.core.instrumentation.events.base import BaseEvent
    from llama_index.core.instrumentation.events.chat_engine import (
        StreamChatDeltaReceivedEvent,
        StreamChatErrorEvent,
    )
    from llama_index.core.instrumentation.events.llm import (
        LLMChatInProgressEvent,
    )
    from llama_index.core.instrumentation.events.span import (
        SpanDropEvent,
    )
    from llama_index.core.instrumentation.span_handlers.base import BaseSpanHandler
except ImportError:
    _import_failed = True
except Exception:
    _import_failed = True

# Module-level shared state
_weave_calls_map: Dict[Union[str, Tuple[Optional[str], str]], Call] = {}
_weave_client_instance: Optional[WeaveClient] = None
_global_root_call: Optional[Call] = None  # Added for global session trace
TRANSFORM_EMBEDDINGS_FLAG: bool = (
    True  # Default to True to enable embedding summarization
)


def get_weave_client() -> WeaveClient:
    global _weave_client_instance
    if _weave_client_instance is None:
        _weave_client_instance = weave_client_context.require_weave_client()
    return _weave_client_instance


def get_embedding_shape(embedding: List[Any]) -> Tuple[int, ...]:
    """Calculates the shape of a (potentially nested) list representing an embedding."""
    shape: List[int] = []
    if not isinstance(embedding, list):
        return ()
    current_level = embedding
    while isinstance(current_level, list):
        shape.append(len(current_level))
        if not current_level:  # Empty list at current level
            break
        current_level = current_level[0] if len(current_level) > 0 else None
    return tuple(shape)


def process_llamaindex_event_start(event: BaseEvent) -> Dict[str, Any]:
    is_event = event.class_name()

    if is_event == "EmbeddingStartEvent":
        return event.model_dump()

def process_llamaindex_event_end(event: BaseEvent) -> Dict[str, Any]:
    return {}


def process_llamaindex_payload(
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if payload is None:
        return {}  # Return empty dict for None payload to simplify call sites

    res = {}
    for k, v in payload.items():
        if (
            TRANSFORM_EMBEDDINGS_FLAG
            and k == "embeddings"
            and isinstance(v, list)
            and v
        ):  # ensure v is not empty
            # Check if it's sparse or dense
            if isinstance(v[0], dict):  # Likely sparse: List[Dict[int, float]]
                first_embedding_info = (
                    f"first has {len(v[0])} non-zero values"
                    if v[0]
                    else "first is empty"
                )
                res[k] = f"{len(v)} sparse embeddings, {first_embedding_info}"
            elif isinstance(v[0], list):  # Likely dense: List[List[float]]
                shapes = [
                    get_embedding_shape(emb) for emb in v if isinstance(emb, list)
                ]
                first_shape_info = (
                    f"first shape: {shapes[0]}"
                    if shapes
                    else "first is not a list or empty"
                )
                res[k] = f"{len(v)} dense embeddings, {first_shape_info}"
            else:  # Fallback for List of other things if any
                res[k] = f"{len(v)} embeddings, first item type: {type(v[0]).__name__}"
        elif k == "chunks" and isinstance(v, list):
            res[k] = (
                f"{len(v)} chunks, first chunk: {str(v[0])[:100]}..."
                if v
                else "0 chunks"
            )
        elif isinstance(v, (list, tuple)) and len(v) > 10:
            res[v] = [str(item)[:100] for item in v[:3]] + [
                f"... ({len(v)-3} more items)"
            ]
        elif isinstance(v, str) and len(v) > 500:
            res[v] = v[:500] + "..."
        else:
            try:
                # Basic check for serializability for JSON
                # Weave client handles full serialization, this is a pre-emptive simplification.
                json.dumps({k: v})
                res[k] = v
            except (TypeError, OverflowError):
                res[k] = str(v)
    return res


def get_op_name_from_event(event: BaseEvent) -> str:
    """Generates a Weave operation name from a LlamaIndex event."""
    class_name = event.class_name()
    core_name = class_name
    for suffix in ["StartEvent", "EndEvent", "Event"]:
        if core_name.endswith(suffix):
            core_name = core_name[: -len(suffix)]
            break

    if core_name:
        return f"llama_index.event.{core_name}"

    snake_case_name = "".join(
        ["_" + i.lower() if i.isupper() else i for i in core_name]
    ).lstrip("_")
    return f"llama_index.unmapped.{snake_case_name}"


def _get_op_name_from_span(span_id: str) -> str:
    # Use only the ClassName.method_name part for the op_name if a hyphen is present
    op_name_base = span_id.split("-")[0] if "-" in span_id else span_id
    return f"llama_index.span.{op_name_base}"


def _remove_common_items(d1, d2):
    result = {}
    for key, value in d2.items():
        if key not in d1:
            result[key] = value
        else:
            if isinstance(value, dict) and isinstance(d1[key], dict):
                # Recursively remove common nested dict items
                nested_diff = _remove_common_items(d1[key], value)
                if nested_diff:  # only include if there's something left
                    result[key] = nested_diff
            elif d1[key] != value:
                result[key] = value
    return result


class WeaveSpanHandler(BaseSpanHandler[Any]):
    """Handles LlamaIndex span start, end, and drop events to trace operations."""

    @classmethod
    def class_name(cls) -> str:
        return "WeaveSpanHandler"

    def _map_args_to_params(
        self,
        instance: Optional[Any],
        bound_args: Any,
        id_: str,
    ) -> Dict[str, Any]:
        """Maps arguments to their parameter names using Python's introspection.
        
        Args:
            instance: The class instance if this is a method call
            bound_args: The BoundArguments object from inspect.signature().bind()
            id_: The span ID which includes the function's qualified name
        
        Returns:
            Dict containing mapped parameters and instance variables
        """
        inputs = {}
        
        # First add any relevant instance variables if this is a method call
        if instance is not None:
            try:
                instance_vars = {
                    k: v for k, v in vars(instance).items() 
                    if not k.startswith('__') and not callable(v) and not isinstance(v, (types.ModuleType, types.FunctionType))
                }
                inputs.update(instance_vars)
                print(f"Weave(SpanHandler): Instance variables captured: {list(instance_vars.keys())}")
            except (TypeError, AttributeError):
                print(f"Weave(SpanHandler): Could not extract instance variables from {type(instance)}")

        # Then add the actual function arguments
        if bound_args is not None:
            # Get the function name from the span ID
            func_name = id_.split(".")[-1].split("-")[0] if "." in id_ else None
            print(f"Weave(SpanHandler): Processing function: {func_name}")
            
            try:
                # Get the raw args and kwargs
                args = getattr(bound_args, 'args', ())
                kwargs = getattr(bound_args, 'kwargs', {})

                if func_name and instance is not None:
                    # Try to get the method from the instance
                    method = getattr(instance, func_name, None)
                    if method is not None:
                        # If it's a bound method, get its original function
                        if hasattr(method, '__func__'):
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
                        
                        print(f"Weave(SpanHandler): Arguments captured: {list(inputs.keys())}")
                    else:
                        print(f"Weave(SpanHandler): Method {func_name} not found on instance")
            except Exception as e:
                print(f"Weave(SpanHandler): Error processing arguments: {str(e)}")

        return inputs

    def new_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Optional[Any] = None,
        parent_span_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Creates a Weave call when a LlamaIndex span starts."""
        gc = get_weave_client()
        op_name = _get_op_name_from_span(id_)

        # print(f"Weave(SpanHandler): New span {id_} with op_name {op_name}")
        # print(f"Weave(SpanHandler): Instance: {instance}")
        # print(f"Weave(SpanHandler): Bound args: {bound_args}")
        # print(f"Weave(SpanHandler): Parent span ID: {parent_span_id}")
        # print(f"Weave(SpanHandler): Tags: {tags}")
        # print(f"Weave(SpanHandler): kwargs: {kwargs}")
        # print("--------------------------------")

        # Map arguments to their parameter names
        raw_combined_inputs = self._map_args_to_params(instance, bound_args, id_)
        
        # Process the inputs through our payload processor
        if raw_combined_inputs:
            try:
                inputs = process_llamaindex_payload(raw_combined_inputs)
            except Exception as e_processing:
                inputs = {
                    "_input_processing_error_": str(e_processing),
                    "_raw_inputs_preview_": str(raw_combined_inputs)[:500] 
                }
        else:
            inputs = {"_info_": "No detailed inputs from instance or bound_args"}

        # Add any tags if present
        if tags:
            inputs['_tags'] = tags

        parent_call = None
        if parent_span_id and parent_span_id in _weave_calls_map:
            parent_call = _weave_calls_map[parent_span_id]
        elif _global_root_call:  # Default to global root call
            parent_call = _global_root_call

        try:
            call = gc.create_call(op_name, inputs, parent_call)
            _weave_calls_map[id_] = call  # Store by full span ID
        except Exception as e:
            print(
                f"Weave(SpanHandler): Error creating call for {op_name} (ID: {id_}): {e}"
            )

    def _prepare_to_exit_or_drop(
        self,
        id_: str,
        result: Optional[Any] = None,
        err: Optional[BaseException] = None,
    ) -> None:
        """Common logic for finishing a Weave call for a LlamaIndex span."""
        gc = get_weave_client()
        if id_ in _weave_calls_map:
            call_to_finish = _weave_calls_map.pop(id_)
            outputs = None
            exception_to_log = err

            if result is not None:
                try:
                    # Pydantic models are common in LlamaIndex results
                    if hasattr(result, "model_dump"):
                        outputs = process_llamaindex_payload(
                            result.model_dump(exclude_none=True)
                        )
                    else:
                        outputs = process_llamaindex_payload({"result": result})
                except Exception:  # Catch serialization errors
                    outputs = process_llamaindex_payload({"result": str(result)})

            try:
                gc.finish_call(call_to_finish, outputs, exception=exception_to_log)
            except Exception as e:
                error_type = "dropping" if err else "finishing"
                print(f"Weave(SpanHandler): Error {error_type} call for ID {id_}: {e}")

    def prepare_to_exit_span(
        self,
        id_: str,
        bound_args: Any,  # Retained for signature compatibility
        instance: Optional[Any] = None,  # Retained
        result: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        """Finishes the Weave call when a LlamaIndex span exits successfully."""
        self._prepare_to_exit_or_drop(id_, result=result)
        return result  # Must return the result per LlamaIndex spec

    def prepare_to_drop_span(
        self,
        id_: str,
        bound_args: Any,  # Retained
        instance: Optional[Any] = None,  # Retained
        err: Optional[BaseException] = None,
        **kwargs: Any,
    ) -> Any:
        """Finishes the Weave call with an error when a LlamaIndex span is dropped."""
        self._prepare_to_exit_or_drop(id_, err=err)
        # Per LlamaIndex, returning None indicates the error is "handled" by this handler.
        return None


class WeaveEventHandler(BaseEventHandler):
    """Handles LlamaIndex events to create fine-grained Weave calls within spans."""

    @classmethod
    def class_name(cls) -> str:
        return "WeaveEventHandler"

    def handle(self, event: BaseEvent) -> None:
        """Processes a LlamaIndex event, creating or finishing a Weave call."""
        gc = get_weave_client()
        op_name = get_op_name_from_event(event)

        # Parent call can be an existing span's call or the global session root
        parent_call_for_event = None
        if (
            event.span_id and event.span_id in _weave_calls_map
        ):  # This refers to span calls map
            parent_call_for_event = _weave_calls_map[event.span_id]
        elif _global_root_call:  # Default to global root call
            parent_call_for_event = _global_root_call

        # Key for pairing Start and End events of the same logical operation within a span
        # Span ID can be None for root-level events not directly tied to an instrumented span
        event_pairing_key: Tuple[Optional[str], str] = (event.span_id, op_name)

        raw_event_payload = {}
        try:
            raw_event_payload = event.model_dump(exclude_none=True)
        except Exception:
            raw_event_payload = {"detail": f"Failed to dump event: {str(event)}"}

        event_class_name = event.class_name()
        is_start_event = event_class_name.endswith("StartEvent")
        is_end_event = event_class_name.endswith("EndEvent")

        try:
            if is_start_event:
                call = gc.create_call(op_name, raw_event_payload, parent_call_for_event)
                _weave_calls_map[event_pairing_key] = call
            elif is_end_event:
                if event_pairing_key in _weave_calls_map:
                    # If the event pairing key is in the weave calls map, finish the call
                    call_to_finish = _weave_calls_map.pop(event_pairing_key)

                    # TODO: ensure it doesn't take a lot of time.
                    event_start_payload = call_to_finish.inputs
                    modified_event_end_payload = _remove_common_items(event_start_payload, raw_event_payload)

                    gc.finish_call(call_to_finish, modified_event_end_payload)
                else:
                    # Fallback for unmatched EndEvent: log as an instantaneous event
                    # print(f"Weave(EventHandler): Unmatched EndEvent for {event_pairing_key}, logging as new.")
                    call = gc.create_call(
                        op_name, raw_event_payload, parent_call_for_event
                    )
                    gc.finish_call(call, raw_event_payload)  # Output is same as input

        except Exception as e:
            print(
                f"Weave(EventHandler): Error processing event {op_name} (Key: {event_pairing_key}): {e}"
            )


def _cleanup_global_root_call():
    """Ensures the global root Weave call is closed on program exit."""
    global _global_root_call
    if _global_root_call:
        try:
            client = get_weave_client()
            client.finish_call(_global_root_call, {"status": "session_ended_at_exit"})
        except Exception:
            # Suppress errors during atexit cleanup to avoid masking other issues.
            # Consider logging to a file if detailed diagnostics are needed here.
            pass
        finally:
            _global_root_call = None


class LLamaIndexPatcher(Patcher):
    """Manages patching of LlamaIndex instrumentation to integrate with Weave."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: Optional[Any] = None  # LlamaIndex dispatcher instance
        self._original_event_handlers: Optional[List[BaseEventHandler]] = None
        self._original_span_handlers: Optional[List[BaseSpanHandler[Any]]] = None
        self.weave_event_handler: Optional[WeaveEventHandler] = None
        self.weave_span_handler: Optional[WeaveSpanHandler] = None
        self._atexit_registered: bool = False

    def _get_script_name(self) -> str:
        """Tries to determine the name of the executing script."""
        try:
            import __main__

            if hasattr(__main__, "__file__") and __main__.__file__:
                return __main__.__file__
        except (ImportError, AttributeError):
            pass  # Ignore errors, fallback to default
        return "unknown_script"

    def attempt_patch(self) -> bool:
        """Attempts to patch LlamaIndex instrumentation and set up Weave handlers."""
        global _global_root_call, _import_failed
        if _import_failed:
            return False

        try:
            import llama_index.core.instrumentation as instrument  # type: ignore

            gc = get_weave_client()  # Initialize client early
            if _global_root_call is None:
                script_name = self._get_script_name()
                _global_root_call = gc.create_call(
                    "llama_index.session",
                    inputs={"script": script_name, "status": "patched"},
                )

            self.dispatcher = instrument.get_dispatcher()
            self._original_event_handlers = list(self.dispatcher.event_handlers)
            self._original_span_handlers = list(self.dispatcher.span_handlers)

            self.weave_event_handler = WeaveEventHandler()
            self.weave_span_handler = WeaveSpanHandler()

            self.dispatcher.add_event_handler(self.weave_event_handler)
            self.dispatcher.add_span_handler(self.weave_span_handler)

            if not self._atexit_registered:
                atexit.register(_cleanup_global_root_call)
                self._atexit_registered = True
                # print("Weave(LlamaIndex): atexit handler registered for global root call.")

        except Exception as e:
            print(f"Weave: Failed to patch LlamaIndex dispatcher: {e}")
            # If patching fails, attempt to clean up any partially created global root call
            if (
                _global_root_call and not _global_root_call.output
            ):  # Check if not already finished
                try:
                    gc.finish_call(
                        _global_root_call, {"status": "patch_failed"}, exception=e
                    )
                except:
                    pass  # Best effort
            _global_root_call = None  # Ensure it's reset
            return False
        return True

    def undo_patch(self) -> bool:
        """Reverts LlamaIndex instrumentation to its original state."""
        global _global_root_call
        if (
            not self.dispatcher
            or self._original_event_handlers is None
            or self._original_span_handlers is None
        ):
            return False

        try:
            self.dispatcher.event_handlers = self._original_event_handlers
            self.dispatcher.span_handlers = self._original_span_handlers

            # Clear local references
            self._original_event_handlers = None
            self._original_span_handlers = None
            self.weave_event_handler = None
            self.weave_span_handler = None
            self.dispatcher = None  # Important to release dispatcher reference

            if _global_root_call:
                client = get_weave_client()
                client.finish_call(
                    _global_root_call, {"status": "unpatched_gracefully"}
                )
                # print(f"Weave(LlamaIndex): Global root call finished: {_global_root_call.id}")
            _global_root_call = None  # Ensure it's reset after finishing

        except Exception as e:
            print(f"Weave: Failed to undo LlamaIndex dispatcher patch: {e}")
            return False
        return True


llamaindex_patcher = LLamaIndexPatcher()
