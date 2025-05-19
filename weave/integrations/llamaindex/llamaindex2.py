from typing import Dict, List, Any, Optional
import json

from weave.integrations.patcher import Patcher
from weave.trace.context import weave_client_context
from weave.trace.weave_client import Call, WeaveClient

import weave

import_failed = False

try:
    from llama_index.core.instrumentation.events.base import BaseEvent
    from llama_index.core.instrumentation.event_handlers.base import BaseEventHandler
    from llama_index.core.instrumentation.span_handlers.base import BaseSpanHandler
    # Import specific event types referenced
    from llama_index.core.instrumentation.events.agent import (
        AgentToolCallEvent,
    )
    from llama_index.core.instrumentation.events.chat_engine import (
        StreamChatErrorEvent,
        StreamChatDeltaReceivedEvent,
    )
    from llama_index.core.instrumentation.events.llm import (
        LLMChatInProgressEvent,
    )
    from llama_index.core.instrumentation.events.span import (
        SpanDropEvent,
    )
    # Other event types will be identified by their class_name()
except ImportError:
    import_failed = True
except Exception:
    import_failed = True
    print(
        "Failed to autopatch llama_index. If you are tracing Llama calls, please upgrade llama_index to be version>=0.10.35"
    )

# Module-level shared state
_weave_calls_map: Dict[str, Call] = {}
_weave_client_instance: Optional[WeaveClient] = None
TRANSFORM_EMBEDDINGS_FLAG: bool = False # Controls detailed embedding logging

def get_weave_client() -> WeaveClient:
    global _weave_client_instance
    if _weave_client_instance is None:
        _weave_client_instance = weave_client_context.require_weave_client()
    return _weave_client_instance

def get_embedding_shape(embedding: list) -> tuple:
    """Get the shape of an embedding."""
    res = []
    if not isinstance(embedding, list):
        return ()
    current_level = embedding
    while isinstance(current_level, list):
        res.append(len(current_level))
        if not current_level:
            break
        current_level = current_level[0] if len(current_level) > 0 else None
    return tuple(res)

def process_llamaindex_payload(
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if payload is None:
        return {} # Return empty dict for None payload to simplify call sites
    
    res = {}
    for k, v in payload.items():
        if TRANSFORM_EMBEDDINGS_FLAG and k == "embeddings" and isinstance(v, list):
            shapes = [get_embedding_shape(emb) for emb in v if isinstance(emb, list)]
            res[k] = f"{len(v)} embeddings, first shape: {shapes[0] if shapes else 'N/A'}"
        elif k == "chunks" and isinstance(v, list):
            res[k] = f"{len(v)} chunks, first chunk: {str(v[0])[:100]}..." if v else "0 chunks"
        elif isinstance(v, (list, tuple)) and len(v) > 10:
             res[k] = [str(item)[:100] for item in v[:3]] + [f"... ({len(v)-3} more items)"]
        elif isinstance(v, str) and len(v) > 500:
            res[k] = v[:500] + "..."
        else:
            try:
                # Basic check for serializability for JSON
                # Weave client handles full serialization, this is a pre-emptive simplification.
                json.dumps({k: v}) 
                res[k] = v
            except (TypeError, OverflowError):
                res[k] = str(v)
    return res

_EVENT_TYPE_TO_OP_NAME_MAP = {
    "Query": "query",
    "Embedding": "embedding",
    "LLMPredict": "llm_predict",
    "LLMStructuredPredict": "llm_structured_predict",
    "LLMCompletion": "llm_completion",
    "LLMChat": "llm_chat",
    "Retrieval": "retrieval",
    "Synthesize": "synthesis",
    "GetResponse": "get_response",
    "ReRank": "rerank",
    "AgentChatWithStep": "agent_chat_with_step",
    "AgentRunStep": "agent_run_step",
    "AgentToolCall": "agent_tool_call",
    "StreamChatDeltaReceived": "stream_chat_delta",
    "LLMChatInProgress": "llm_chat_in_progress",
    "StreamChatError": "stream_chat_error",
    "SpanDrop": "span_drop",
}

def get_op_name_from_event(event: BaseEvent) -> str:
    class_name = event.class_name()
    core_name = class_name
    for suffix in ["StartEvent", "EndEvent", "Event"]:
        if core_name.endswith(suffix):
            core_name = core_name[:-len(suffix)]
            break
            
    if core_name in _EVENT_TYPE_TO_OP_NAME_MAP:
        return f"llama_index.{_EVENT_TYPE_TO_OP_NAME_MAP[core_name]}"

    snake_case_name = ''.join(['_' + i.lower() if i.isupper() else i for i in core_name]).lstrip('_')
    return f"llama_index.unmapped.{snake_case_name}"


class WeaveSpanHandler(BaseSpanHandler[Any]):
    @classmethod
    def class_name(cls) -> str:
        return "WeaveSpanHandler"

    def new_span(
        self,
        id_: str,
        bound_args: Any, 
        instance: Optional[Any] = None,
        parent_span_id: Optional[str] = None,
        tags: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        gc = get_weave_client()
        op_name = f"llama_index.span.{id_}" # id_ is often "ClassName.method_name"

        inputs = {}
        if bound_args:
            try:
                # Attempt to serialize args and kwargs. Fallback to string for safety.
                inputs["args"] = [str(arg) for arg in bound_args.args]
                inputs["kwargs"] = {k: str(v) for k, v in bound_args.kwargs.items()}
                inputs = process_llamaindex_payload(inputs)
            except Exception: # Catch any serialization errors
                 inputs = {"args": str(bound_args.args), "kwargs": str(bound_args.kwargs)}
        
        parent_call = _weave_calls_map.get(parent_span_id) if parent_span_id else None
        
        try:
            call = gc.create_call(op_name, inputs, parent_call)
            _weave_calls_map[id_] = call
        except Exception as e:
            print(f"Weave(SpanHandler): Error creating call for {op_name}: {e}")
        return None

    def prepare_to_exit_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Optional[Any] = None,
        result: Optional[Any] = None,
        **kwargs: Any,
    ) -> Any:
        gc = get_weave_client()
        if id_ in _weave_calls_map:
            call = _weave_calls_map.pop(id_)
            outputs = {}
            if result is not None:
                try:
                    # If result is a Pydantic model (common in LlamaIndex)
                    if hasattr(result, 'model_dump'):
                        outputs = process_llamaindex_payload(result.model_dump(exclude_none=True))
                    else: # Fallback for other types
                        outputs = process_llamaindex_payload({"result": result})
                except Exception: # Catch any serialization errors
                    outputs = process_llamaindex_payload({"result": str(result)})

            try:
                gc.finish_call(call, outputs)
            except Exception as e:
                print(f"Weave(SpanHandler): Error finishing call for {id_}: {e}")
        return result

    def prepare_to_drop_span(
        self,
        id_: str,
        bound_args: Any,
        instance: Optional[Any] = None,
        err: Optional[BaseException] = None,
        **kwargs: Any,
    ) -> Any:
        gc = get_weave_client()
        if id_ in _weave_calls_map:
            call = _weave_calls_map.pop(id_)
            try:
                gc.finish_call(call, None, exception=err)
            except Exception as e:
                print(f"Weave(SpanHandler): Error dropping call for {id_}: {e}")
        return None # Indicates error is "handled"


class WeaveEventHandler(BaseEventHandler):
    @classmethod
    def class_name(cls) -> str:
        return "WeaveEventHandler"

    def handle(self, event: BaseEvent) -> None:
        gc = get_weave_client()
        parent_span_call = _weave_calls_map.get(event.span_id) if event.span_id else None

        event_id = event.id_
        op_name = get_op_name_from_event(event)
        
        raw_payload = {}
        try:
            raw_payload = event.model_dump(exclude_none=True)
        except Exception: # Fallback if model_dump fails or not available
            raw_payload = {"detail": str(event)}
        
        processed_payload = process_llamaindex_payload(raw_payload)

        is_start_event = event.class_name().endswith("StartEvent")
        is_end_event = event.class_name().endswith("EndEvent")
        
        try:
            if is_start_event:
                call = gc.create_call(op_name, processed_payload, parent_span_call)
                _weave_calls_map[event_id] = call
            elif is_end_event:
                if event_id in _weave_calls_map:
                    call = _weave_calls_map.pop(event_id)
                    gc.finish_call(call, processed_payload)
                else:
                    # Log an instantaneous event if no corresponding start
                    # print(f"Weave(EventHandler): EndEvent for {event_id} without start, logging.")
                    call = gc.create_call(op_name, processed_payload, parent_span_call)
                    gc.finish_call(call, processed_payload) # Finishes with its own payload as output
            elif isinstance(event, (AgentToolCallEvent, StreamChatDeltaReceivedEvent, LLMChatInProgressEvent, StreamChatErrorEvent, SpanDropEvent)):
                # Atomic, informational or error events
                exception_obj = None
                if isinstance(event, StreamChatErrorEvent) and hasattr(event, 'exception') and event.exception: # type: ignore
                    exception_obj = event.exception # type: ignore
                elif isinstance(event, SpanDropEvent) and hasattr(event, 'err_str') and event.err_str: # type: ignore
                    exception_obj = Exception(event.err_str) # type: ignore
                
                call = gc.create_call(op_name, processed_payload, parent_span_call)
                if exception_obj:
                    gc.finish_call(call, None, exception=exception_obj)
                else:
                    gc.finish_call(call, processed_payload) # Output is same as input for these
            else: # Generic/unclassified events
                # print(f"Weave(EventHandler): Generic event {op_name}, logging.")
                call = gc.create_call(op_name, processed_payload, parent_span_call)
                gc.finish_call(call, processed_payload)
        except Exception as e:
            print(f"Weave(EventHandler): Error processing event {op_name} ({event_id}): {e}")

# Removed the old handle_events function as its purpose is integrated into WeaveEventHandler


class LLamaIndexPatcher(Patcher):
    def __init__(self) -> None:
        super().__init__() # Ensure Patcher's __init__ is called if it has one
        self.dispatcher = None
        self._original_event_handlers: Optional[List[BaseEventHandler]] = None
        self._original_span_handlers: Optional[List[BaseSpanHandler[Any]]] = None
        self.weave_event_handler: Optional[WeaveEventHandler] = None
        self.weave_span_handler: Optional[WeaveSpanHandler] = None


    def attempt_patch(self) -> bool:
        if import_failed:
            return False
        try:
            import llama_index.core.instrumentation as instrument

            self.dispatcher = instrument.get_dispatcher()
            
            self._original_event_handlers = list(self.dispatcher.event_handlers)
            self._original_span_handlers = list(self.dispatcher.span_handlers) # type: ignore

            self.weave_event_handler = WeaveEventHandler()
            self.weave_span_handler = WeaveSpanHandler()

            self.dispatcher.add_event_handler(self.weave_event_handler)
            self.dispatcher.add_span_handler(self.weave_span_handler) # type: ignore
        except Exception as e:
            print(f"Weave: Failed to patch LlamaIndex dispatcher: {e}")
            return False
        else:
            return True

    def undo_patch(self) -> bool:
        if not self.dispatcher or self._original_event_handlers is None or self._original_span_handlers is None:
            return False
        try:
            # Check if our handlers are present before trying to remove by object equality
            # More robust: restore the original lists directly.
            self.dispatcher.event_handlers = self._original_event_handlers
            self.dispatcher.span_handlers = self._original_span_handlers # type: ignore
            
            # Clear references
            self._original_event_handlers = None
            self._original_span_handlers = None
            self.weave_event_handler = None
            self.weave_span_handler = None
            self.dispatcher = None
        except Exception as e:
            print(f"Weave: Failed to undo LlamaIndex dispatcher patch: {e}")
            return False
        else:
            return True


llamaindex_patcher = LLamaIndexPatcher()
