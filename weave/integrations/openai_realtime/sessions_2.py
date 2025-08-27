"""
OpenAI Realtime API Session Management and Tracing

This module handles real-time conversation sessions with the OpenAI Realtime API,
managing audio/text accumulation, trace lifecycle, and event processing.
"""

import base64
from collections.abc import Callable
import io
import json
import time
import uuid
import wave
import logging
from dataclasses import dataclass, field
from enum import Enum
from threading import Timer
from typing import Any, Dict, List, Optional, Union

from weave import Content
from weave.trace.context import weave_client_context

from .encoding import pcm_to_wav

from .models import (
    ServerMessageType,
    Session,
    SessionCreatedMessage,
    SessionUpdateMessage,
    SessionUpdateParams,
    SessionUpdatedMessage,
    InputAudioBufferSpeechStartedMessage,
    InputAudioBufferSpeechStoppedMessage,
    InputAudioBufferAppendMessage,
    InputAudioBufferCommittedMessage,
    InputAudioBufferClearedMessage,
    ItemCreatedMessage,
    ItemInputAudioTranscriptionDeltaMessage,
    ItemInputAudioTranscriptionCompletedMessage,
    ResponseCreatedMessage,
    ResponseOutputItemAddedMessage,
    ResponseTextDeltaMessage,
    ResponseTextDoneMessage,
    ResponseAudioDeltaMessage,
    ResponseAudioDoneMessage,
    ResponseAudioTranscriptDeltaMessage,
    ResponseAudioTranscriptDoneMessage,
    ResponseDoneMessage,
    ResponseFunctionCallArgumentsDeltaMessage,
    ResponseFunctionCallArgumentsDoneMessage,
    create_message_from_dict,
)
logger = logging.getLogger(__name__)



class ItemRole(Enum):
    """Conversation item roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class ItemContent:
    """Content within a conversation item."""
    type: str
    text: Optional[str] = None
    audio_bytes: Optional[bytes] = None
    audio_format: Optional[str] = None

    def add_text_delta(self, delta: str) -> None:
        """Append text delta to existing text."""
        if self.text is None:
            self.text = ""
        self.text += delta

    def add_audio_delta(self, base64_audio: str) -> None:
        """Decode and append audio bytes."""
        if self.audio_bytes is None:
            self.audio_bytes = b""
        self.audio_bytes += base64.b64decode(base64_audio)

    def set_final_transcript(self, transcript: str) -> None:
        """Replace accumulated transcript with final version."""
        self.text = transcript

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for trace submission."""
        result: dict[str, Any] = {"type": self.type}

        if self.type == "text" and self.text:
            result["text"] = self.text
        elif self.type == "audio" and self.audio_bytes:
            audio_content = Content.from_bytes(
                pcm_to_wav(self.audio_bytes),
                extension="wav",
                mimetype="audio/wav"
            )
            result["audio"] = {
                "data": audio_content,
                "format": "wav"
            }

        return result


@dataclass
class ConversationItem:
    """Represents a single conversation item (message, function call, etc.)."""
    id: str
    type: str
    role: Optional[ItemRole] = None
    content: List[ItemContent] = field(default_factory=list)
    name: Optional[str] = None  # For function calls
    call_id: Optional[str] = None  # For function calls
    arguments: Optional[str] = None  # For function calls
    output: Optional[str] = None  # For function call outputs

    def add_content(self, content: ItemContent) -> None:
        """Add content part to this item."""
        self.content.append(content)

    def get_or_create_content(self, index: int, content_type: str) -> ItemContent:
        """Get content at index or create if it doesn't exist."""
        while len(self.content) <= index:
            self.content.append(ItemContent(type=content_type))
        return self.content[index]

    def add_audio_delta(self, base64_audio: str, index: int = 0) -> None:
        """Add audio delta to content at specified index."""
        content = self.get_or_create_content(index, "audio")
        content.add_audio_delta(base64_audio)

    def add_text_delta(self, delta: str, index: int = 0) -> None:
        """Add text delta to content at specified index."""
        content = self.get_or_create_content(index, "text")
        content.add_text_delta(delta)

    def add_transcript_delta(self, delta: str, index: int = 0) -> None:
        """Add transcript delta to content at specified index."""
        self.add_text_delta(delta, index)

    def set_final_transcript(self, transcript: str, index: int = 0) -> None:
        """Set final transcript for content at specified index."""
        content = self.get_or_create_content(index, "text")
        content.text = transcript

    def to_message_dict(self) -> dict[str, Any]:
        """Convert to message format for trace submission."""
        message: dict[str, Any] = {"role": self.role.value if self.role else "user"}

        if self.type == "function_call":
            message["tool_calls"] = [{
                "id": self.call_id,
                "type": "function",
                "function": {
                    "name": self.name,
                    "arguments": self.arguments or ""
                }
            }]
        elif self.type == "function_call_output":
            message["role"] = "tool"
            message["content"] = self.output or ""
            message["tool_call_id"] = self.call_id
        else:
            # Regular message with content
            if len(self.content) == 1 and self.content[0].type == "text":
                # Single text content can be simplified
                message["content"] = self.content[0].text or ""
            else:
                # Multi-modal or audio content
                message["content"] = [c.to_dict() for c in self.content]
        
        return message


@dataclass
class ConversationTurn:
    """Manages a single conversation turn (user input + assistant response)."""
    id: str
    user_item: Optional[ConversationItem] = None
    assistant_items: List[ConversationItem] = field(default_factory=list)
    weave_call: Optional[Any] = None
    debounce_timer: Optional[Timer] = None
    pending_tool_calls: List[str] = field(default_factory=list)
    tool_call_traces: Dict[str, Any] = field(default_factory=dict)
    
    def add_assistant_item(self, item: ConversationItem) -> None:
        """Add an assistant response item to this turn."""
        self.assistant_items.append(item)
    
    def has_audio_input(self) -> bool:
        """Check if user input contains audio."""
        if not self.user_item:
            return False
        return any(c.type == "audio" for c in self.user_item.content)
    
    def _create_weave_call(self, session: 'WeaveSession') -> None:
        """Create the Weave trace for this conversation turn."""
        if self.weave_call:
            return
        
        # Build input messages
        messages = []
        for item in session.conversation_history:
            messages.append(item.to_message_dict())
        
        # Add current user input
        if self.user_item:
            messages.append(self.user_item.to_message_dict())
        
        # Build input parameters
        inputs = {
            "messages": messages,
            "model": session.model or "gpt-4o-realtime",
        }
        
        if session.tools:
            inputs["tools"] = session.tools
        
        if session.tool_choice:
            inputs["tool_choice"] = session.tool_choice
        
        if session.temperature:
            inputs["temperature"] = session.temperature
        
        if session.max_response_output_tokens:
            inputs["max_tokens"] = session.max_response_output_tokens
        
        if session.voice:
            inputs["voice"] = session.voice
        
        if session.modalities:
            inputs["modalities"] = list(session.modalities)
        
        # Create the Weave call
        wc = weave_client_context.require_weave_client()
        self.weave_call = wc.create_call("conversation_turn", inputs)
    
    def schedule_trace_creation(self, session: 'WeaveSession', delay: float = 1.0) -> None:
        """Schedule debounced trace creation for audio input."""
        if self.debounce_timer:
            self.debounce_timer.cancel()
        
        self.debounce_timer = Timer(delay, lambda: self._create_weave_call(session))
        self.debounce_timer.start()
    
    def cancel_debounce(self, session: 'WeaveSession') -> None:
        """Cancel debounced trace creation and create immediately."""
        if self.debounce_timer:
            self.debounce_timer.cancel()
            self.debounce_timer = None
        self._create_weave_call(session)
    
    def create_tool_call_trace(self, call_id: str, name: str, arguments: str) -> None:
        """Create a child trace for a tool call execution."""
        if not self.weave_call:
            return

        inputs = {
            "name": name,
            "arguments": json.loads(arguments) if arguments else {}
        }

        wc = weave_client_context.require_weave_client()
        tool_trace = wc.create_call("function_call_execution", inputs, parent=self.weave_call)
        self.tool_call_traces[call_id] = tool_trace

    def complete_tool_call_trace(self, call_id: str, output: str) -> None:
        """Complete a tool call trace with output."""
        if call_id in self.tool_call_traces:
            wc = weave_client_context.require_weave_client()
            wc.finish_call(self.tool_call_traces[call_id], {"output": output})
            del self.tool_call_traces[call_id]

            # Remove from pending tool calls
            if call_id in self.pending_tool_calls:
                self.pending_tool_calls.remove(call_id)

    def complete(self, session: 'WeaveSession', usage: Optional[Dict] = None) -> None:
        """Finalize this conversation turn."""
        if not self.weave_call:
            return

        # Don't finalize if there are pending tool calls
        if self.pending_tool_calls:
            return

        # Build output structure
        output = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "model": session.model or "gpt-4o-realtime",
            "created": int(time.time()),
            "object": "chat.completion",
            "choices": []
        }

        if usage:
            output["usage"] = usage

        # Add assistant responses as choices
        for item in self.assistant_items:
            choice = {
                "message": item.to_message_dict(),
                "finish_reason": "tool_calls" if item.type == "function_call" else "stop"
            }
            
            if item.type == "function_call":
                choice["tool_calls"] = [{
                    "id": item.call_id,
                    "type": "function",
                    "function": {
                        "name": item.name,
                        "arguments": item.arguments or ""
                    }
                }]
            
            output["choices"].append(choice)
        
        # Finish the Weave call
        wc = weave_client_context.require_weave_client()
        wc.finish_call(self.weave_call, output)

        # Add items to conversation history
        if self.user_item:
            session.conversation_history.append(self.user_item)
        session.conversation_history.extend(self.assistant_items)


@dataclass
class WeaveSession:
    """Extended session with conversation history and turn management."""
    session: Session  # Composition instead of inheritance
    conversation_history: List[ConversationItem] = field(default_factory=list)
    current_turn: Optional[ConversationTurn] = None
    current_user_item: Optional[ConversationItem] = None
    current_response_items: Dict[str, ConversationItem] = field(default_factory=dict)
    
    # Delegate access to Session fields
    @property
    def id(self) -> str:
        return self.session.id
    
    @property
    def model(self) -> str:
        return self.session.model
    
    @property
    def modalities(self):
        return self.session.modalities
    
    @property
    def instructions(self):
        return self.session.instructions
    
    @property
    def voice(self):
        return self.session.voice
    
    @property
    def input_audio_format(self):
        return self.session.input_audio_format
    
    @property
    def output_audio_format(self):
        return self.session.output_audio_format
    
    @property
    def input_audio_transcription(self):
        return self.session.input_audio_transcription
    
    @property
    def turn_detection(self):
        return self.session.turn_detection
    
    @property
    def tools(self):
        return self.session.tools
    
    @property
    def tool_choice(self):
        return self.session.tool_choice
    
    @property
    def temperature(self):
        return self.session.temperature
    
    @property
    def max_response_output_tokens(self):
        return self.session.max_response_output_tokens

    @classmethod
    def from_session(cls, session: Session) -> 'WeaveSession':
        """Create WeaveSession from Session object."""
        return cls(session=session)
    
    def update_config(self, config: SessionUpdateParams | Session) -> None:
        """Update session configuration from SessionUpdateParams."""
        if config.model is not None:
            self.session.model = config.model
        if config.tools is not None:
            self.session.tools = config.tools
        if config.tool_choice is not None:
            self.session.tool_choice = config.tool_choice
        if config.temperature is not None:
            self.session.temperature = config.temperature
        if config.max_response_output_tokens is not None:
            self.session.max_response_output_tokens = config.max_response_output_tokens
        if config.voice is not None:
            self.session.voice = config.voice
        if config.modalities is not None:
            self.session.modalities = config.modalities
        if config.instructions is not None:
            self.session.instructions = config.instructions
        if config.input_audio_format is not None:
            self.session.input_audio_format = config.input_audio_format
        if config.output_audio_format is not None:
            self.session.output_audio_format = config.output_audio_format
        if config.input_audio_transcription is not None:
            self.session.input_audio_transcription = config.input_audio_transcription
        if config.turn_detection is not None:
            self.session.turn_detection = config.turn_detection


class SessionManager:
    """Manages multiple conversation sessions and event dispatch."""
    sessions: dict[str, WeaveSession] = {}
    event_handlers: dict[str, Callable]
    active_session: Optional[str]

    def __init__(self):
        self.sessions: Dict[str, WeaveSession] = {}
        self.active_session: Optional[str] = None
        self.event_handlers = self._register_event_handlers()

    def _register_event_handlers(self) -> Dict[str, Any]:
        """Register event type to handler method mapping."""
        return {
            "session.created": self._handle_session_created,
            "session.updated": self._handle_session_updated,
            "input_audio_buffer.speech_started": self._handle_speech_started,
            "input_audio_buffer.speech_stopped": self._handle_speech_stopped,
            "input_audio_buffer.append": self._handle_audio_append,
            "input_audio_buffer.committed": self._handle_audio_committed,
            "input_audio_buffer.cleared": self._handle_audio_cleared,
            "conversation.item.created": self._handle_item_created,
            "conversation.item.input_audio_transcription.delta": self._handle_transcript_delta,
            "conversation.item.input_audio_transcription.completed": self._handle_transcript_completed,
            "response.created": self._handle_response_created,
            "response.output_item.added": self._handle_output_item_added,
            "response.text.delta": self._handle_text_delta,
            "response.text.done": self._handle_text_done,
            "response.audio.delta": self._handle_audio_delta,
            "response.audio.done": self._handle_audio_done,
            "response.audio_transcript.delta": self._handle_audio_transcript_delta,
            "response.audio_transcript.done": self._handle_audio_transcript_done,
            "response.function_call_arguments.delta": self._handle_function_arguments_delta,
            "response.function_call_arguments.done": self._handle_function_arguments_done,
            "response.done": self._handle_response_done,
            "session.update": self._handle_session_updated
        }
    
    def process_event(self, event_data: Dict[str, Any]) -> None:
        """Process a server event."""
        event = create_message_from_dict(event_data)
        event_type = event.type

        # Dispatch to appropriate handler
        handler = self.event_handlers.get(event_type)
        if handler:
            handler(event)

    def _get_session(self, session_id: Optional[str] = None) -> WeaveSession | None:
        """Get or create a session."""
        if not session_id:
            session_id = self.active_session
        if not session_id:
            return None
        return self.sessions.get(session_id)

    def _handle_session_created(self, event: SessionCreatedMessage) -> None:
        """Handle session creation."""
        self.sessions[event.session.id] = WeaveSession.from_session(event.session)
        self.active_session = event.session.id

    def _handle_session_updated(self, event: Union[SessionUpdatedMessage, SessionUpdateMessage]) -> None:
        """Handle session update."""
        session = self._get_session()
        if not session:
            # If this is a client-side session.update (SessionUpdateMessage) and no session exists,
            # we should just ignore it since the session will be created when we receive session.created
            if isinstance(event, SessionUpdateMessage):
                logger.warning("Received session.update before session creation - ignoring")
                return
            # For SessionUpdatedMessage from server, this shouldn't happen
            session_id = getattr(event.session, 'id', self.active_session)
            raise ValueError(f"_handle_session_updated - Failed to get session {session_id} - Session does not exist")
        session.update_config(event.session)

    def _handle_speech_started(self, event: InputAudioBufferSpeechStartedMessage) -> None:
        """Handle speech start - create user item."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_speech_started - No current session")

        session.current_user_item = ConversationItem(
            id=event.item_id,
            type="message",
            role=ItemRole.USER
        )
        # Add audio content placeholder
        session.current_user_item.add_content(ItemContent(type="audio"))

    def _handle_speech_stopped(self, event: InputAudioBufferSpeechStoppedMessage) -> None:
        """Handle speech stop."""
        # Speech has stopped, but item isn't committed yet
        pass

    def _handle_audio_append(self, event: InputAudioBufferAppendMessage) -> None:
        """Handle audio buffer append."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_audio_append - No current session")
        if session.current_user_item:
            session.current_user_item.add_audio_delta(event.audio)

    def _handle_audio_committed(self, event: InputAudioBufferCommittedMessage) -> None:
        """Handle audio buffer commit - start new turn."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_audio_committed - No current session")

        # Create new conversation turn
        turn = ConversationTurn(
            id=event.item_id,
            user_item=session.current_user_item
        )
        session.current_turn = turn

        # Schedule or create trace based on input type
        if turn.has_audio_input():
            # Debounce for audio to wait for final transcript
            turn.schedule_trace_creation(session, delay=1.0)
        else:
            # Create trace immediately for text input
            turn._create_weave_call(session)

        # Clear current user item
        session.current_user_item = None

    def _handle_audio_cleared(self, event: InputAudioBufferClearedMessage) -> None:
        """Handle audio buffer clear."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_audio_cleared - No current session")
        session.current_user_item = None
    
    def _handle_item_created(self, event: ItemCreatedMessage) -> None:
        """Handle conversation item creation."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_item_created - No current session")
        item = event.item
        
        # Check if this is a function call output
        if item.type == "function_call_output":
            # Create trace for tool execution
            if session.current_turn and item.call_id:
                session.current_turn.create_tool_call_trace(
                    item.call_id,
                    "function_execution",
                    "{}"
                )
                # Complete with output
                session.current_turn.complete_tool_call_trace(
                    item.call_id,
                    item.output or ""
                )
    
    def _handle_transcript_delta(self, event: ItemInputAudioTranscriptionDeltaMessage) -> None:
        """Handle transcript delta."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_transcript_delta - No current session")
        if session.current_user_item and event.item_id == session.current_user_item.id:
            session.current_user_item.add_transcript_delta(event.delta, event.content_index)
        elif session.current_turn and session.current_turn.user_item:
            if event.item_id == session.current_turn.user_item.id:
                session.current_turn.user_item.add_transcript_delta(event.delta, event.content_index)
    
    def _handle_transcript_completed(self, event: ItemInputAudioTranscriptionCompletedMessage) -> None:
        """Handle transcript completion."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_transcript_completed - No current session")
        
        # Update the appropriate item's transcript
        if session.current_user_item and event.item_id == session.current_user_item.id:
            session.current_user_item.set_final_transcript(event.transcript, event.content_index)
        elif session.current_turn and session.current_turn.user_item:
            if event.item_id == session.current_turn.user_item.id:
                session.current_turn.user_item.set_final_transcript(event.transcript, event.content_index)
                # Cancel debounce and create trace immediately
                session.current_turn.cancel_debounce(session)
    
    def _handle_response_created(self, event: ResponseCreatedMessage) -> None:
        """Handle response creation."""
        # Response has started but no items yet
        pass
    
    def _handle_output_item_added(self, event: ResponseOutputItemAddedMessage) -> None:
        """Handle output item addition."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_output_item_added - No current session")
        item_data = event.item
        
        # Create conversation item
        item = ConversationItem(
            id=item_data.id or f"item_{uuid.uuid4().hex[:8]}",
            type=item_data.type,
            role=ItemRole.ASSISTANT
        )
        
        # Handle function calls
        if item_data.type == "function_call":
            item.name = item_data.name
            item.call_id = item_data.call_id
            item.arguments = item_data.arguments
            # Track pending tool call
            if session.current_turn:
                session.current_turn.pending_tool_calls.append(item_data.call_id)
        
        # Store in session for delta updates
        session.current_response_items[item.id] = item
        
        # Add to current turn
        if session.current_turn:
            session.current_turn.add_assistant_item(item)
    
    def _handle_text_delta(self, event: ResponseTextDeltaMessage) -> None:
        """Handle text delta."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_text_delta - No current session")
        if event.item_id in session.current_response_items:
            item = session.current_response_items[event.item_id]
            item.add_text_delta(event.delta, event.content_index)
    
    def _handle_text_done(self, _: ResponseTextDoneMessage) -> None:
        """Handle text completion."""
        # Text is already accumulated via deltas
        pass
    
    def _handle_audio_delta(self, event: ResponseAudioDeltaMessage) -> None:
        """Handle audio delta."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_audio_delta - No current session")
        if event.item_id in session.current_response_items:
            item = session.current_response_items[event.item_id]
            item.add_audio_delta(event.delta, event.content_index)
    
    def _handle_audio_done(self, _: ResponseAudioDoneMessage) -> None:
        """Handle audio completion."""
        # Audio is already accumulated via deltas
        pass
    
    def _handle_audio_transcript_delta(self, event: ResponseAudioTranscriptDeltaMessage) -> None:
        """Handle audio transcript delta."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_audio_transcript_delta - No current session")
        if event.item_id in session.current_response_items:
            item = session.current_response_items[event.item_id]
            item.add_transcript_delta(event.delta, event.content_index)

    def _handle_audio_transcript_done(self, event: ResponseAudioTranscriptDoneMessage) -> None:
        """Handle audio transcript completion."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_audio_transcript_done - No current session")
        if event.item_id in session.current_response_items:
            item = session.current_response_items[event.item_id]
            item.set_final_transcript(event.transcript, event.content_index)

    def _handle_function_arguments_delta(self, event: ResponseFunctionCallArgumentsDeltaMessage) -> None:
        """Handle function arguments delta."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_function_arguments_delta - No current session")
        if event.item_id in session.current_response_items:
            item = session.current_response_items[event.item_id]
            if item.arguments is None:
                item.arguments = ""
            item.arguments += event.delta
    
    def _handle_function_arguments_done(self, event: ResponseFunctionCallArgumentsDoneMessage) -> None:
        """Handle function arguments completion."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_function_arguments_done - No current session")
        if event.item_id in session.current_response_items:
            item = session.current_response_items[event.item_id]
            item.name = event.name
            item.arguments = event.arguments
    
    def _handle_response_done(self, event: ResponseDoneMessage) -> None:
        """Handle response completion."""
        session = self._get_session()
        if not session:
            raise RuntimeError(f"_handle_response_done - No current session")

        # Extract usage information
        usage = None
        if event.response.usage:
            usage = {
                "total_tokens": event.response.usage.total_tokens,
                "input_tokens": event.response.usage.input_tokens,
                "output_tokens": event.response.usage.output_tokens,
            }
        
        # Complete the turn if no pending tool calls
        if session.current_turn:
            session.current_turn.complete(session, usage)
        
        # Clear response items
        session.current_response_items.clear()
