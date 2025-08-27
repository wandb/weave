import base64
import io
import json
import threading
import uuid
import wave
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional, Union

import weave
from weave import Content

# Re-export ItemStatus for backward compatibility
class ItemStatus:
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

from .models import (
    AudioFormat,
    Modality,
    Voice,
    MessageRole,
    ItemParamStatus,
    ResponseItemStatus,
    ResponseStatus,
    InputAudioTranscription,
    TurnDetection,
    ServerVAD,
    NoTurnDetection,
    ToolsDefinition,
    ToolChoice,
    Temperature,
    SessionUpdateParams,
    Session as ModelSession,
    SessionCreatedMessage,
    SessionUpdatedMessage,
    InputAudioBufferAppendMessage,
    InputAudioBufferSpeechStartedMessage,
    InputAudioBufferSpeechStoppedMessage,
    InputAudioBufferCommittedMessage,
    InputAudioBufferClearMessage,
    ItemCreatedMessage,
    ItemTruncatedMessage,
    ItemDeletedMessage,
    ItemInputAudioTranscriptionCompletedMessage,
    ItemInputAudioTranscriptionDeltaMessage,
    ItemInputAudioTranscriptionFailedMessage,
    ResponseCreatedMessage,
    ResponseDoneMessage,
    ResponseOutputItemAddedMessage,
    ResponseOutputItemDoneMessage,
    ResponseContentPartAddedMessage,
    ResponseContentPartDoneMessage,
    ResponseAudioDeltaMessage,
    ResponseAudioDoneMessage,
    ResponseTextDeltaMessage,
    ResponseTextDoneMessage,
    ResponseAudioTranscriptDeltaMessage,
    ResponseAudioTranscriptDoneMessage,
    ResponseFunctionCallArgumentsDeltaMessage,
    ResponseFunctionCallArgumentsDoneMessage,
    ResponseMessageItem,
    ResponseFunctionCallItem,
    ResponseFunctionCallOutputItem,
    ResponseItem,
    ResponseItemContentPart,
    Response,
    Usage,
    MessageItem,
    SystemMessageItem,
    UserMessageItem,
    AssistantMessageItem,
    FunctionCallItem,
    FunctionCallOutputItem,
    Item,
    InputTextContentPart,
    InputAudioContentPart,
    OutputTextContentPart,
    UserContentPart,
    AssistantContentPart,
    create_server_message_from_dict,
    create_user_message_from_dict,
)


def pcm_to_wav(
    pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2
) -> bytes:
    """Convert raw PCM audio data to WAV format.

    Args:
        pcm_data: Raw PCM audio bytes (little-endian 16-bit PCM)
        sample_rate: Sample rate in Hz (default 24000 for OpenAI Realtime)
        channels: Number of channels (default 1 for mono)
        sample_width: Sample width in bytes (default 2 for 16-bit)

    Returns:
        WAV formatted audio bytes
    """
    # Ensure we have valid PCM data
    if not pcm_data or len(pcm_data) == 0:
        # Return minimal valid WAV file with no audio data
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"")
        wav_buffer.seek(0)
        return wav_buffer.getvalue()

    # Ensure the PCM data length is even (for 16-bit samples)
    if len(pcm_data) % 2 != 0:
        # Pad with a zero byte if odd length
        pcm_data = pcm_data + b"\x00"

    # Create WAV file in memory using wave module for correct formatting
    wav_buffer = io.BytesIO()

    with wave.open(wav_buffer, "wb") as wav_file:
        # Set WAV parameters
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)

        # Write the PCM data as frames
        wav_file.writeframes(pcm_data)

    # Get the WAV data
    wav_buffer.seek(0)
    return wav_buffer.getvalue()




@dataclass
class ItemContent:
    """Content within a conversation item."""

    type: Literal["audio", "text", "audio_text"]
    text: Optional[str] = None
    audio_bytes: Optional[bytes] = None  # Accumulated audio bytes
    transcript: Optional[str] = None
    audio_start_ms: Optional[int] = None
    audio_end_ms: Optional[int] = None
    audio_format: Optional[AudioFormat] = None

    def get_audio_content(self) -> Optional[Content]:
        """Convert audio bytes to Content object."""
        if self.audio_bytes and len(self.audio_bytes) > 0:
            # Debug: Log audio data size and format
            # print(f"Debug: Converting audio - format: {self.audio_format}, size: {len(self.audio_bytes)} bytes")

            # Convert PCM to WAV format for browser compatibility
            if self.audio_format == "pcm16":
                wav_data = pcm_to_wav(self.audio_bytes, sample_rate=24000)
                return Content.from_bytes(
                    wav_data, extension="wav", mimetype="audio/wav"
                )
            elif self.audio_format in ["g711_ulaw", "g711_alaw"]:
                # For G.711 formats, we'd need a different conversion
                # For now, return the raw data with appropriate MIME type
                return Content.from_bytes(
                    self.audio_bytes,
                    extension="raw",
                    mimetype="audio/basic",
                    metadata={"format": self.audio_format},
                )
            else:
                # Default: try to convert as PCM
                wav_data = pcm_to_wav(self.audio_bytes, sample_rate=24000)
                return Content.from_bytes(
                    wav_data, extension="wav", mimetype="audio/wav"
                )
        return None


@dataclass
class ConversationTurn:
    """Represents a complete turn in the conversation (user input + assistant response)."""

    id: str
    user_item: Optional["ConversationItem"] = None
    assistant_item: Optional["ConversationItem"] = None
    weave_call: Optional[Any] = None  # The weave call object
    status: ResponseItemStatus = "in_progress"
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    pending_function_calls: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )  # Store function calls by call_id
    _debounce_timer: Optional[threading.Timer] = field(
        default=None, init=False, repr=False
    )  # Timer for debounced call creation
    _session_ref: Optional[Any] = field(
        default=None, init=False, repr=False
    )  # Reference to the session
    _stored_response_data: Optional[dict[str, Any]] = field(
        default=None, init=False, repr=False
    )  # Store response data for later completion

    def complete(self, response_data: Optional[dict[str, Any]] = None) -> None:
        """Mark the turn as completed."""
        self.status = "completed"
        self.completed_at = datetime.now()
        if self.weave_call:
            # Finish the weave call with the complete conversation turn data
            outputs = self._get_outputs(response_data)
            from weave.trace.context.weave_client_context import get_weave_client

            client = get_weave_client()
            if client:
                client.finish_call(self.weave_call, output=outputs)

    def _get_outputs(
        self, response_data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Get the outputs for the weave call in OpenAI API format."""
        outputs = {}

        # Build choices array from assistant response
        choices = []
        if self.assistant_item:
            # Build message using the same format as get_message_history
            text_content = self.assistant_item.get_full_text()
            audio_content = self.assistant_item.get_audio_content()

            message: dict[str, Any] = {"role": "assistant"}

            # Format content the same way as input messages
            if self.assistant_item.has_audio() and text_content:
                # Multi-modal assistant response (text + audio)
                content_parts: list[dict[str, Any]] = []

                # Add text part
                content_parts.append({"type": "text", "text": text_content})

                # Add audio part using the same structure
                if audio_content:
                    content_parts.append(
                        {
                            "type": "audio",
                            "audio": {"data": audio_content, "format": "wav"},
                        }
                    )

                message["content"] = content_parts

            elif self.assistant_item.has_audio() and not text_content:
                # Audio-only response
                if audio_content:
                    message["content"] = [
                        {
                            "type": "audio",
                            "audio": {"data": audio_content, "format": "wav"},
                        }
                    ]
                else:
                    message["content"] = None

            elif text_content:
                # Text-only response
                message["content"] = text_content
            else:
                message["content"] = None

            # Add assistant-specific fields
            message["refusal"] = None
            message["annotations"] = []
            message["function_call"] = None

            # Add tool calls if present
            if self.assistant_item.tool_calls:
                message["tool_calls"] = self.assistant_item.tool_calls
            else:
                message["tool_calls"] = None

            choices.append(
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "stop"
                    if not self.pending_function_calls
                    else "tool_calls",
                }
            )

        # Add response metadata if available
        if response_data:
            outputs["id"] = response_data.get("id", f"chatcmpl-{uuid.uuid4().hex[:16]}")
            outputs["model"] = response_data.get("model", "gpt-4o-realtime")
            outputs["created"] = response_data.get("created")
            outputs["object"] = "chat.completion"
            outputs["usage"] = response_data.get("usage", {})

        outputs["choices"] = choices
        return outputs

    def schedule_weave_call_creation(self, delay_ms: int = 1000) -> None:
        """Schedule the creation of a weave call with a delay to allow transcripts to arrive."""
        # Cancel any existing timer
        if self._debounce_timer:
            self._debounce_timer.cancel()

        # Schedule the call creation
        self._debounce_timer = threading.Timer(
            delay_ms / 1000.0, self._create_weave_call
        )
        self._debounce_timer.start()

    def cancel_debounce(self) -> None:
        """Cancel any pending debounced call creation."""
        if self._debounce_timer:
            self._debounce_timer.cancel()
            self._debounce_timer = None

    def _create_weave_call(self) -> None:
        """Create the weave call for this turn."""
        if not self._session_ref or self.weave_call:
            return  # Already created or no session

        session = self._session_ref
        with weave.thread(session.id):
            from weave.trace.context.weave_client_context import get_weave_client

            client = get_weave_client()
            if client:
                # Build inputs in OpenAI API format
                messages = session.conversation.get_message_history()

                # Add system message if configured
                if session.config.instructions:
                    system_message = {
                        "role": "system",
                        "content": session.config.instructions,
                    }
                    messages = [system_message] + messages

                # Determine model based on modalities
                model = (
                    "gpt-4o-realtime"
                    if "audio" in session.config.modalities
                    else "gpt-4o"
                )

                inputs = {
                    "self": {
                        "client": {
                            "base_url": "https://api.openai.com/v1/",
                            "version": "1.0.0",
                        }
                    },
                    "messages": messages,
                    "model": model,
                }

                # Add tools if configured
                if session.config.tools:
                    inputs["tools"] = session.config.tools
                    inputs["tool_choice"] = session.config.tool_choice

                # Add modalities
                inputs["modalities"] = session.config.modalities

                # Add other config options
                inputs["temperature"] = session.config.temperature
                inputs["max_tokens"] = session.config.max_response_output_tokens
                inputs["voice"] = session.config.voice

                # Create the call
                call = client.create_call(op=conversation_turn, inputs=inputs)
                self.weave_call = call


@dataclass
class ConversationItem:
    id: str
    role: Union[MessageRole, Literal["tool"]]  # MessageRole doesn't have "tool", so we keep it separate
    status: ResponseItemStatus
    content: list[ItemContent] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    previous_item_id: Optional[str] = None
    tool_call_id: Optional[str] = None  # For tool response messages
    tool_name: Optional[str] = None  # For tool response messages
    tool_calls: Optional[list[dict[str, Any]]] = (
        None  # For assistant messages with tool calls
    )

    def add_audio_delta(self, audio_base64: str) -> None:
        """Add audio delta base64 string to the item's audio content."""
        # Decode the base64 chunk to bytes
        try:
            # Ensure proper base64 padding
            if isinstance(audio_base64, str):
                # Add padding if needed
                missing_padding = len(audio_base64) % 4
                if missing_padding:
                    audio_base64 += "=" * (4 - missing_padding)

            audio_bytes = base64.b64decode(audio_base64)
        except Exception as e:
            print(f"Warning: Failed to decode audio base64: {e}")
            return

        for content_part in self.content:
            if content_part.type in ["audio", "audio_text"]:
                if content_part.audio_bytes is None:
                    content_part.audio_bytes = audio_bytes
                else:
                    content_part.audio_bytes += audio_bytes
                return
        # If no audio content exists, create one
        # Default to pcm16 format if not already specified
        self.content.append(
            ItemContent(type="audio", audio_bytes=audio_bytes, audio_format="pcm16")
        )

    def add_text_delta(self, text: str) -> None:
        """Add text delta to the item's text content."""
        for content_part in self.content:
            if content_part.type in ["text", "audio_text"]:
                if content_part.text is None:
                    content_part.text = text
                else:
                    content_part.text += text
                return
        # If no text content exists, create one
        self.content.append(ItemContent(type="text", text=text))

    def add_transcript_delta(self, transcript: str) -> None:
        """Add transcript delta to the item's audio content."""
        for content_part in self.content:
            if content_part.type in ["audio", "audio_text"]:
                if content_part.transcript is None:
                    content_part.transcript = transcript
                else:
                    content_part.transcript += transcript
                return

    def set_audio_timing(self, start_ms: Optional[int], end_ms: Optional[int]) -> None:
        """Set audio timing information."""
        for content_part in self.content:
            if content_part.type in ["audio", "audio_text"]:
                if start_ms is not None:
                    content_part.audio_start_ms = start_ms
                if end_ms is not None:
                    content_part.audio_end_ms = end_ms
                return

    def complete(self) -> None:
        """Mark the item as completed."""
        self.status = "completed"

    def has_audio(self) -> bool:
        """Check if the item contains audio content."""
        # Check for audio content type, not just bytes (bytes may arrive later)
        return any(c.type in ["audio", "audio_text"] for c in self.content)

    def has_text(self) -> bool:
        """Check if the item contains text content."""
        return any(
            c.type in ["text", "audio_text"] and (c.text or c.transcript)
            for c in self.content
        )

    def get_full_text(self) -> Optional[str]:
        """Get the full text content (including transcripts)."""
        texts = []
        for content_part in self.content:
            if content_part.text:
                texts.append(content_part.text)
            elif content_part.transcript:
                texts.append(content_part.transcript)
        return " ".join(texts) if texts else None

    def get_audio_content(self) -> Optional[Content]:
        """Get the audio content as a Content object."""
        for content_part in self.content:
            if (
                content_part.type in ["audio", "audio_text"]
                and content_part.audio_bytes
            ):
                return content_part.get_audio_content()
        return None


@dataclass
class Conversation:
    id: str
    items: list[ConversationItem] = field(default_factory=list)
    turns: list[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    current_turn: Optional[ConversationTurn] = None

    def add_item(self, item: ConversationItem) -> None:
        """Add a conversation item."""
        if self.items:
            item.previous_item_id = self.items[-1].id
        self.items.append(item)

    def get_item(self, item_id: str) -> Optional[ConversationItem]:
        """Get a conversation item by ID."""
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_latest_item(self) -> Optional[ConversationItem]:
        """Get the latest conversation item."""
        return self.items[-1] if self.items else None

    def get_user_items(self) -> list[ConversationItem]:
        """Get all user conversation items."""
        return [item for item in self.items if item.role == "user"]

    def get_assistant_items(self) -> list[ConversationItem]:
        """Get all assistant conversation items."""
        return [item for item in self.items if item.role == "assistant"]

    def start_turn(self, turn_id: str) -> ConversationTurn:
        """Start a new conversation turn."""
        turn = ConversationTurn(id=turn_id)
        self.turns.append(turn)
        self.current_turn = turn
        return turn

    def get_turn(self, turn_id: str) -> Optional[ConversationTurn]:
        """Get a turn by ID."""
        for turn in self.turns:
            if turn.id == turn_id:
                return turn
        return None

    def complete_current_turn(
        self, response_data: Optional[dict[str, Any]] = None
    ) -> None:
        """Complete the current turn."""
        if self.current_turn:
            self.current_turn.complete(response_data)
            self.current_turn = None

    def get_message_history(self) -> list[dict[str, Any]]:
        """Build the complete message history for the conversation."""
        messages = []

        for item in self.items:
            if item.status != "completed":
                continue

            message: dict[str, Any] = {"role": item.role if isinstance(item.role, str) else item.role.value}

            # Build content based on what the item contains
            text_content = item.get_full_text()
            audio_content = item.get_audio_content()

            # For user messages with both text and audio, create multi-part content
            if item.role == "user" and item.has_audio() and text_content:
                content_parts: list[dict[str, Any]] = []

                # Add text part
                content_parts.append({"type": "text", "text": text_content})

                # Add audio part
                if audio_content:
                    content_parts.append(
                        {
                            "type": "audio",
                            "audio": {"data": audio_content, "format": "wav"},
                        }
                    )

                message["content"] = content_parts

            # For user messages with only audio
            elif item.role == "user" and item.has_audio() and not text_content:
                if audio_content:
                    message["content"] = [
                        {
                            "type": "audio",
                            "audio": {"data": audio_content, "format": "wav"},
                        }
                    ]
                else:
                    message["content"] = None

            # For assistant messages with both text and audio, create multi-part content
            elif item.role == "assistant" and item.has_audio() and text_content:
                content_parts = []

                # Add text part
                content_parts.append({"type": "text", "text": text_content})

                # Add audio part
                if audio_content:
                    content_parts.append(
                        {
                            "type": "audio",
                            "audio": {"data": audio_content, "format": "wav"},
                        }
                    )

                message["content"] = content_parts

            # For assistant messages with only audio
            elif item.role == "assistant" and item.has_audio() and not text_content:
                if audio_content:
                    message["content"] = [
                        {
                            "type": "audio",
                            "audio": {"data": audio_content, "format": "wav"},
                        }
                    ]
                else:
                    message["content"] = None

            # For messages with only text
            elif text_content:
                message["content"] = text_content
            else:
                message["content"] = None

            # Add tool-specific fields
            if item.role == "tool":
                message["tool_call_id"] = item.tool_call_id
                message["name"] = item.tool_name

            # Add assistant-specific fields
            elif item.role == "assistant":
                message["refusal"] = None
                message["annotations"] = []
                message["function_call"] = None
                message["tool_calls"] = item.tool_calls  # Add tool calls if present

            messages.append(message)

        return messages


@dataclass
class SessionConfig:
    modalities: list[Modality] = field(default_factory=lambda: ["text", "audio"])
    instructions: str = "You are a helpful assistant."
    voice: Voice = "alloy"
    input_audio_format: AudioFormat = "pcm16"
    output_audio_format: AudioFormat = "pcm16"
    input_audio_transcription: Optional[InputAudioTranscription] = None
    turn_detection: Optional[TurnDetection] = None
    temperature: float = 0.8
    max_response_output_tokens: Union[str, int] = "inf"
    tools: ToolsDefinition = field(default_factory=list)
    tool_choice: ToolChoice = "auto"


@dataclass
class Session:
    id: str
    config: SessionConfig
    conversation: Conversation
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[int] = None
    current_response_id: Optional[str] = None
    current_item_id: Optional[str] = None

    def update_config(self, **kwargs: Any) -> None:
        """Update session configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

    def start_user_input(self, item_id: str) -> ConversationItem:
        """Start a new user input item."""
        item = ConversationItem(
            id=item_id, role="user", status="in_progress"
        )
        self.conversation.add_item(item)
        self.current_item_id = item_id
        return item

    def start_assistant_response(
        self, item_id: str, response_id: str
    ) -> ConversationItem:
        """Start a new assistant response item."""
        item = ConversationItem(
            id=item_id, role="assistant", status="in_progress"
        )
        self.conversation.add_item(item)
        self.current_item_id = item_id
        self.current_response_id = response_id
        return item

    def complete_current_item(self) -> None:
        """Complete the current conversation item."""
        if self.current_item_id:
            item = self.conversation.get_item(self.current_item_id)
            if item:
                item.complete()
        self.current_item_id = None
        self.current_response_id = None


@weave.op
def conversation_turn() -> dict[str, Any]:
    """Op for tracking a single conversation turn in OpenAI Realtime."""
    # This op is created when user input is committed
    # It will be finished when the assistant response is complete
    # The actual processing happens asynchronously via websocket events
    # Inputs are passed as kwargs to match OpenAI API format
    return {"status": "in_progress"}


@weave.op
def function_call_execution(
    function_name: str, arguments: dict[str, Any], call_id: str
) -> dict[str, Any]:
    """Op for tracking function call execution in OpenAI Realtime."""
    # This op is created when a function call output is sent
    # The actual function execution happens in the client
    return {
        "function_name": function_name,
        "arguments": arguments,
        "call_id": call_id,
        "status": "executed",
    }


class SessionManager:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.active_session_id: Optional[str] = None

    def create_session(
        self, session_id: str, config: Optional[SessionConfig] = None
    ) -> Session:
        """Create a new session."""
        if config is None:
            config = SessionConfig()

        conversation = Conversation(id=f"{session_id}")
        session = Session(id=session_id, config=config, conversation=conversation)
        self.sessions[session_id] = session
        self.active_session_id = session_id
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def get_active_session(self) -> Optional[Session]:
        """Get the currently active session."""
        if self.active_session_id:
            return self.sessions.get(self.active_session_id)
        return None

    def set_active_session(self, session_id: str) -> bool:
        """Set the active session."""
        if session_id in self.sessions:
            self.active_session_id = session_id
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            if self.active_session_id == session_id:
                self.active_session_id = None
            return True
        return False

    def process_event(self, event: dict[str, Any]) -> Optional[Any]:
        """Process an incoming event and update the session state."""
        event_type = event.get("type")
        session = self.get_active_session()

        if not session and event_type not in ["session.created", "session.update"]:
            return None

        # Session events
        if event_type == "session.created":
            session_data = event.get("session", {})
            session_id = session_data.get("id")
            if session_id:
                # Parse modalities - already list of strings matching Modality type
                modalities = session_data.get("modalities", ["text", "audio"])

                # Parse voice - already a string matching Voice type
                voice = session_data.get("voice", "alloy")

                # Parse audio formats - already strings matching AudioFormat type
                input_format = session_data.get("input_audio_format", "pcm16")
                output_format = session_data.get("output_audio_format", "pcm16")

                # Parse input audio transcription
                transcription_raw = session_data.get("input_audio_transcription")
                transcription = InputAudioTranscription(**transcription_raw) if transcription_raw else None

                # Parse turn detection
                turn_detection_raw = session_data.get("turn_detection")
                turn_detection = None
                if turn_detection_raw:
                    if turn_detection_raw.get("type") == "server_vad":
                        turn_detection = ServerVAD(**turn_detection_raw)
                    else:
                        turn_detection = NoTurnDetection(**turn_detection_raw)

                config = SessionConfig(
                    modalities=modalities,
                    instructions=session_data.get("instructions", ""),
                    voice=voice,
                    input_audio_format=input_format,
                    output_audio_format=output_format,
                    input_audio_transcription=transcription,
                    turn_detection=turn_detection,
                    temperature=session_data.get("temperature", 0.8),
                    max_response_output_tokens=session_data.get(
                        "max_response_output_tokens", "inf"
                    ),
                    tools=session_data.get("tools", []),
                    tool_choice=session_data.get("tool_choice", "auto"),
                )
                session = self.create_session(session_id, config)
                session.expires_at = session_data.get("expires_at")
                return session

        elif event_type == "session.updated" and session:
            session_data = event.get("session", {})
            session.update_config(**session_data)
            return session

        # Input audio buffer events
        elif event_type == "input_audio_buffer.append":
            # This is a client event - user is sending audio to the server
            if not session:
                return None
            audio_base64 = event.get("audio")
            if audio_base64 and session.current_item_id:
                # Only store audio if we have an active item (speech has started)
                # This prevents accumulating silence/noise before speech
                item = session.conversation.get_item(session.current_item_id)
                if item and item.role == "user":
                    item.add_audio_delta(audio_base64)
            # Don't buffer audio before speech starts - let server VAD handle it
            return None

        elif event_type == "input_audio_buffer.speech_started":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            audio_start_ms = event.get("audio_start_ms")  # Server-side timing info
            if item_id:
                item = session.start_user_input(item_id)
                # Get audio format from session config
                audio_format = session.config.input_audio_format if session else "pcm16"
                item.content.append(
                    ItemContent(
                        type="audio",
                        audio_start_ms=audio_start_ms,
                        audio_format=audio_format,
                    )
                )

                # Don't apply any buffered audio - server VAD handles prefix_padding_ms
                # We only collect audio AFTER speech_started is received

                return item

        elif event_type == "input_audio_buffer.speech_stopped":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            audio_end_ms = event.get("audio_end_ms")
            if item_id:
                item = session.conversation.get_item(item_id)
                if item:
                    item.set_audio_timing(None, audio_end_ms)
                return item

        elif event_type == "input_audio_buffer.clear":
            # Clear any current item when buffer is cleared
            # This happens when the server interrupts or clears the buffer
            if session and session.current_item_id:
                # We may want to handle incomplete items here
                pass
            return None

        elif event_type == "input_audio_buffer.committed":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            if item_id:
                item = session.conversation.get_item(item_id)
                if item:
                    item.complete()
                    # Start a new conversation turn when user input is committed
                    turn = session.conversation.start_turn(turn_id=item_id)
                    turn.user_item = item
                    turn._session_ref = session

                    # Schedule debounced weave call creation to wait for transcripts
                    # If the item has audio content, wait for transcript to arrive
                    if item.has_audio():
                        turn.schedule_weave_call_creation(delay_ms=1000)
                    else:
                        # For text-only items, create the call immediately
                        turn._create_weave_call()
                return item

        # Conversation item events
        elif event_type == "conversation.item.created":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_data = event.get("item", {})
            item_id = item_data.get("id")
            item_type = item_data.get("type")
            role = item_data.get("role")
            status = item_data.get("status", "in_progress")

            # Handle function call output items
            if item_type == "function_call_output":
                call_id = item_data.get("call_id")
                output = item_data.get("output")

                # Create a tool message item in the conversation
                if call_id and session.conversation.current_turn:
                    turn = session.conversation.current_turn

                    # Get the function info from pending calls
                    function_info = turn.pending_function_calls.get(call_id, {})
                    function_name = function_info.get("name", "unknown_function")
                    arguments = function_info.get("arguments", "{}")

                    # Create a tool response item in the conversation
                    tool_item = ConversationItem(
                        id=item_id,
                        role="tool",  # Tool role is not in MessageRole
                        status="completed",
                        tool_call_id=call_id,
                        tool_name=function_name,
                    )
                    tool_item.content.append(ItemContent(type="text", text=output))
                    session.conversation.add_item(tool_item)

                    # Parse arguments if they're a string
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except:
                            arguments = {"raw": arguments}

                    # Create a child call for the function execution
                    if turn.weave_call:
                        with weave.thread(session.id):
                            from weave.trace.context.weave_client_context import (
                                get_weave_client,
                            )

                            client = get_weave_client()
                            if client:
                                func_inputs = {
                                    "function_name": function_name,
                                    "arguments": arguments,
                                    "call_id": call_id,
                                }
                                func_call = client.create_call(
                                    op=function_call_execution,
                                    inputs=func_inputs,
                                    parent=turn.weave_call,
                                )
                                # Immediately finish the function call with the output
                                func_outputs = {"result": output, "call_id": call_id}
                                client.finish_call(func_call, output=func_outputs)

                                # Remove from pending calls
                                turn.pending_function_calls.pop(call_id, None)

                                # If no more pending function calls, complete the turn
                                if not turn.pending_function_calls and hasattr(
                                    turn, "_stored_response_data"
                                ):
                                    # Complete the turn with the stored response data
                                    turn.complete(turn._stored_response_data)
                                    session.conversation.current_turn = None

                return None

            if item_id and role:
                existing_item = session.conversation.get_item(item_id)
                if not existing_item:
                    item = ConversationItem(
                        id=item_id,
                        role=role,  # Already a string, will be validated by type
                        status="completed" if status == "completed" else "in_progress",
                    )

                    # Process content
                    content_list = item_data.get("content", [])
                    for content_data in content_list:
                        content_type = content_data.get("type")
                        if content_type == "audio":
                            # Check if audio data is provided as base64
                            audio_data = content_data.get("audio")
                            audio_bytes = None
                            if audio_data:
                                try:
                                    audio_bytes = base64.b64decode(audio_data)
                                except Exception:
                                    pass
                            # Determine format based on role
                            audio_format = (
                                session.config.input_audio_format
                                if role == "user"
                                else session.config.output_audio_format
                            )
                            item.content.append(
                                ItemContent(
                                    type="audio",
                                    audio_bytes=audio_bytes,
                                    transcript=content_data.get("transcript"),
                                    audio_format=audio_format,
                                )
                            )
                        elif content_type == "text":
                            item.content.append(
                                ItemContent(
                                    type="text", text=content_data.get("text", "")
                                )
                            )

                    session.conversation.add_item(item)

                    # If this is a user item and it's already complete, start a turn
                    if role == "user" and status == "completed":
                        turn = session.conversation.start_turn(turn_id=item_id)
                        turn.user_item = item
                        turn._session_ref = session

                        # Schedule debounced weave call creation to wait for transcripts
                        # If the item has audio content, wait for transcript to arrive
                        if item.has_audio():
                            turn.schedule_weave_call_creation(delay_ms=1000)
                        else:
                            # For text-only items, create the call immediately
                            turn._create_weave_call()

                    return item
                return existing_item

        elif event_type == "conversation.item.input_audio_transcription.delta":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            transcript_delta = event.get("delta")
            if item_id and transcript_delta:
                item = session.conversation.get_item(item_id)
                if item:
                    item.add_transcript_delta(transcript_delta)
                return item

        elif event_type == "conversation.item.input_audio_transcription.completed":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            transcript = event.get("transcript")
            if item_id and transcript:
                item = session.conversation.get_item(item_id)
                if item:
                    # Replace the accumulated transcript with the final complete version
                    for content_part in item.content:
                        if content_part.type in ["audio", "audio_text"]:
                            content_part.transcript = transcript
                            break

                    # If there's a turn with a pending debounce, cancel it and create the call now
                    existing_turn: Optional[ConversationTurn] = (
                        session.conversation.get_turn(item_id)
                    )
                    if existing_turn and existing_turn._debounce_timer:
                        existing_turn.cancel_debounce()
                        existing_turn._create_weave_call()

                return item

        # Response events
        elif event_type == "response.created":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            response_data = event.get("response", {})
            response_id = response_data.get("id")
            if response_id:
                session.current_response_id = response_id
                return response_data

        elif event_type == "response.output_item.added":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_data = event.get("item", {})
            item_id = item_data.get("id")
            response_id = event.get("response_id")
            if item_id and response_id:
                item = session.start_assistant_response(item_id, response_id)
                # Associate assistant item with current turn
                if session.conversation.current_turn:
                    session.conversation.current_turn.assistant_item = item
                return item

        elif event_type == "response.content_part.added":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            part = event.get("part", {})
            if item_id:
                item = session.conversation.get_item(item_id)
                if item:
                    part_type = part.get("type")
                    if part_type == "audio":
                        audio_format = (
                            session.config.output_audio_format if session else "pcm16"
                        )
                        item.content.append(
                            ItemContent(type="audio", audio_format=audio_format)
                        )
                    elif part_type == "text":
                        item.content.append(ItemContent(type="text", text=""))
                return item

        # Delta events
        elif event_type == "response.audio.delta":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            audio_delta = event.get("delta")
            if item_id and audio_delta:
                item = session.conversation.get_item(item_id)
                if item:
                    item.add_audio_delta(audio_delta)
                return item

        elif event_type == "response.text.delta":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            text_delta = event.get("delta")
            if item_id and text_delta:
                item = session.conversation.get_item(item_id)
                if item:
                    item.add_text_delta(text_delta)
                return item

        elif event_type == "response.audio_transcript.delta":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id")
            transcript_delta = event.get("delta")
            if item_id and transcript_delta:
                item = session.conversation.get_item(item_id)
                if item:
                    item.add_transcript_delta(transcript_delta)
                return item

        # Completion events
        elif event_type == "response.done":
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            session.complete_current_item()

            # Complete the current conversation turn
            if session.conversation.current_turn:
                turn = session.conversation.current_turn

                # Build response data in OpenAI format
                response_data = {
                    "id": event.get("response", {}).get(
                        "id", f"chatcmpl-{uuid.uuid4().hex[:16]}"
                    ),
                    "model": "gpt-4o-realtime",
                    "created": event.get("response", {}).get("created"),
                    "usage": event.get("response", {}).get("usage", {}),
                }

                # Extract tool/function calls from output items
                tool_calls_list = []
                if "response" in event and "output" in event["response"]:
                    for output_item in event["response"]["output"]:
                        item_type = output_item.get("type")

                        if item_type == "function_call":
                            call_id = output_item.get("call_id")
                            # Store function call info in the turn for later tracking
                            if turn and call_id:
                                turn.pending_function_calls[call_id] = {
                                    "name": output_item.get("name"),
                                    "arguments": output_item.get("arguments"),
                                }
                                # Also add to tool calls list for the assistant message
                                tool_calls_list.append(
                                    {
                                        "id": call_id,
                                        "type": "function",
                                        "function": {
                                            "name": output_item.get("name"),
                                            "arguments": output_item.get("arguments"),
                                        },
                                    }
                                )

                # Store tool calls in the assistant item
                if turn.assistant_item and tool_calls_list:
                    turn.assistant_item.tool_calls = tool_calls_list

                # Only finish the call if there are no pending function calls
                # If there are pending function calls, we'll finish the call when they complete
                if not turn.pending_function_calls:
                    turn.complete(response_data)
                    session.conversation.current_turn = None
                else:
                    # Store the response data for later when function calls complete
                    if not hasattr(turn, "_stored_response_data"):
                        turn._stored_response_data = response_data

            return event.get("response")

        elif event_type in ["response.output_item.done", "conversation.item.done"]:
            if not session:
                print(f"Error: No active session for event {event_type}")
                return None
            item_id = event.get("item_id") or (event.get("item", {}).get("id"))
            if item_id:
                item = session.conversation.get_item(item_id)
                if item:
                    item.complete()
                return item

        return None
