import atexit
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
    from llama_index.core.instrumentation.events.base import BaseEvent
    from llama_index.core.instrumentation.events.span import SpanDropEvent
    from llama_index.core.instrumentation.span_handlers.base import BaseSpanHandler
except ImportError:
    _import_failed = True
except Exception:
    _import_failed = True

# Module-level shared state
_weave_calls_map: Dict[Union[str, Tuple[Optional[str], str]], Call] = {}
_weave_client_instance: Optional[WeaveClient] = None
_global_root_call: Optional[Call] = None


def get_weave_client() -> WeaveClient:
    global _weave_client_instance
    if _weave_client_instance is None:
        _weave_client_instance = weave_client_context.require_weave_client()
    return _weave_client_instance


def _convert_instance_to_dict(obj: Any) -> Any:
    """Convert a class instance to a dict if possible."""
    if hasattr(obj, "model_dump"):  # Handle pydantic models
        return obj.model_dump(exclude_none=True)
    elif hasattr(obj, "__dict__"):  # Handle regular class instances
        return {k: v for k, v in vars(obj).items() 
                if not k.startswith('__') and not callable(v)}
    return obj


def _get_class_name(obj: Any) -> str:
    """Get a meaningful class name from an object."""
    # Try class_name() method first (common in LlamaIndex)
    if hasattr(obj, "class_name") and callable(obj.class_name):
        return obj.class_name()
    # Try class name from the class itself
    return obj.__class__.__name__


def _process_inputs(raw_inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Process inputs to ensure JSON serializability and handle special cases."""
    processed = {}
    
    for k, v in raw_inputs.items():
        # Handle lists of instances
        if isinstance(v, (list, tuple)) and len(v) > 0:
            # Check if list contains class instances
            first_item = v[0]
            if hasattr(first_item, "__class__") and not isinstance(first_item, (str, int, float, bool, dict, list, tuple)):
                # Convert list of instances to dict with class names as keys
                processed[k] = {
                    f"{_get_class_name(item)}_{i}": _convert_instance_to_dict(item)
                    for i, item in enumerate(v)
                }
                continue
        
        # Handle single instances
        if hasattr(v, "__class__") and not isinstance(v, (str, int, float, bool, dict, list, tuple)):
            processed[k] = _convert_instance_to_dict(v)
            continue
            
        # Ensure JSON serializability for other types
        try:
            json.dumps(v)
            processed[k] = v
        except (TypeError, OverflowError):
            processed[k] = str(v)
    
    return processed


def _get_op_name_from_span(span_id: str) -> str:
    """Get operation name from span ID."""
    op_name_base = span_id.split("-")[0] if "-" in span_id else span_id
    return f"llama_index.span.{op_name_base}"


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
        """Maps arguments to their parameter names using Python's introspection."""
        inputs = {}
        
        # First add any relevant instance variables if this is a method call
        if instance is not None:
            try:
                instance_vars = {
                    k: v for k, v in vars(instance).items() 
                    if not k.startswith('__') and not callable(v) and not isinstance(v, (types.ModuleType, types.FunctionType))
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
            except Exception:
                pass

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

        # Map arguments to their parameter names
        raw_combined_inputs = self._map_args_to_params(instance, bound_args, id_)
        
        # Process the inputs - just ensure JSON serializability
        inputs = _process_inputs(raw_combined_inputs)

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
            print(f"Weave(SpanHandler): Error creating call for {op_name} (ID: {id_}): {e}")

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
                        outputs = _process_inputs(result.model_dump(exclude_none=True))
                    else:
                        outputs = _process_inputs({"result": result})
                except Exception:  # Catch serialization errors
                    outputs = _process_inputs({"result": str(result)})

            try:
                gc.finish_call(call_to_finish, outputs, exception=exception_to_log)
            except Exception as e:
                error_type = "dropping" if err else "finishing"
                print(f"Weave(SpanHandler): Error {error_type} call for ID {id_}: {e}")

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


class WeaveEventHandler(BaseEventHandler):
    """Handles LlamaIndex events to create fine-grained Weave calls within spans."""

    @classmethod
    def class_name(cls) -> str:
        return "WeaveEventHandler"

    def _get_base_event_name(self, event_class_name: str) -> str:
        """Get the base event name without Start/End suffix."""
        for suffix in ["StartEvent", "EndEvent", "Event"]:
            if event_class_name.endswith(suffix):
                return event_class_name[:-len(suffix)]
        return event_class_name

    def handle(self, event: BaseEvent) -> None:
        """Processes a LlamaIndex event, creating or finishing a Weave call."""
        gc = get_weave_client()
        event_class_name = event.class_name()
        
        # Get base event name (e.g., "Embedding" from "EmbeddingStartEvent")
        base_event_name = self._get_base_event_name(event_class_name)
        op_name = f"llama_index.event.{base_event_name}"

        # Parent call can be an existing span's call or the global session root
        parent_call_for_event = None
        if event.span_id and event.span_id in _weave_calls_map:
            parent_call_for_event = _weave_calls_map[event.span_id]
        elif _global_root_call:
            parent_call_for_event = _global_root_call

        # Key for pairing Start and End events
        event_pairing_key: Tuple[Optional[str], str] = (event.span_id, op_name)

        try:
            raw_event_payload = event.model_dump(exclude_none=True)
        except Exception:
            raw_event_payload = {"detail": str(event)}

        is_start_event = event_class_name.endswith("StartEvent")
        is_end_event = event_class_name.endswith("EndEvent")

        try:
            if is_start_event:
                # Create a new call for the start event
                call = gc.create_call(op_name, raw_event_payload, parent_call_for_event)
                _weave_calls_map[event_pairing_key] = call
            elif is_end_event:
                # Try to find the matching start event call
                if event_pairing_key in _weave_calls_map:
                    # Found matching start event, finish its call with end event data
                    call_to_finish = _weave_calls_map.pop(event_pairing_key)
                    gc.finish_call(call_to_finish, raw_event_payload)
                else:
                    # No matching start event found, create a standalone call
                    # This is not ideal but better than losing the event
                    print(f"Weave(EventHandler): Warning - Unmatched end event {event_class_name}")
                    call = gc.create_call(op_name, raw_event_payload, parent_call_for_event)
                    gc.finish_call(call, raw_event_payload)
            else:
                # Handle non-start/end events as instantaneous events
                call = gc.create_call(op_name, raw_event_payload, parent_call_for_event)
                gc.finish_call(call, raw_event_payload)
        except Exception as e:
            print(f"Weave(EventHandler): Error processing event {op_name} (Key: {event_pairing_key}): {e}")


def _cleanup_global_root_call():
    """Ensures the global root Weave call is closed on program exit."""
    global _global_root_call
    if _global_root_call:
        try:
            client = get_weave_client()
            client.finish_call(_global_root_call, {"status": "session_ended_at_exit"})
        except Exception:
            pass
        finally:
            _global_root_call = None


class LLamaIndexPatcher(Patcher):
    """Manages patching of LlamaIndex instrumentation to integrate with Weave."""

    def __init__(self) -> None:
        super().__init__()
        self.dispatcher: Optional[Any] = None
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
            pass
        return "unknown_script"

    def attempt_patch(self) -> bool:
        """Attempts to patch LlamaIndex instrumentation and set up Weave handlers."""
        global _global_root_call, _import_failed
        if _import_failed:
            return False

        try:
            import llama_index.core.instrumentation as instrument

            gc = get_weave_client()
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

        except Exception as e:
            print(f"Weave: Failed to patch LlamaIndex dispatcher: {e}")
            if _global_root_call and not _global_root_call.output:
                try:
                    gc.finish_call(_global_root_call, {"status": "patch_failed"}, exception=e)
                except:
                    pass
            _global_root_call = None
            return False
        return True

    def undo_patch(self) -> bool:
        """Reverts LlamaIndex instrumentation to its original state."""
        global _global_root_call
        if not self.dispatcher or self._original_event_handlers is None or self._original_span_handlers is None:
            return False

        try:
            self.dispatcher.event_handlers = self._original_event_handlers
            self.dispatcher.span_handlers = self._original_span_handlers

            self._original_event_handlers = None
            self._original_span_handlers = None
            self.weave_event_handler = None
            self.weave_span_handler = None
            self.dispatcher = None

            if _global_root_call:
                client = get_weave_client()
                client.finish_call(_global_root_call, {"status": "unpatched_gracefully"})
            _global_root_call = None

        except Exception as e:
            print(f"Weave: Failed to undo LlamaIndex dispatcher patch: {e}")
            return False
        return True


llamaindex_patcher = LLamaIndexPatcher()
