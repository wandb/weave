from abc import abstractmethod
import asyncio
import base64
import binascii
from dataclasses import dataclass
from typing import Generic, Literal, Optional, Type, TypeVar, Union
from weave.type_wrappers.Content import Content
from encoding import pcm_to_wav

# Import the models from the models.py file
import models

UserMessageType = models.InputAudioBufferAppendMessage | models.UnknownClientMessage
ServerMessageType = (
    models.InputAudioBufferSpeechStartedMessage |
    models.InputAudioBufferSpeechStoppedMessage |
    models.ResponseTextDeltaMessage |
    models.ResponseTextDoneMessage |
    models.ResponseFunctionCallArgumentsDeltaMessage |
    models.ResponseFunctionCallArgumentsDoneMessage |
    models.ResponseAudioDeltaMessage |
    models.ResponseAudioDoneMessage |
    models.ResponseAudioTranscriptDeltaMessage |
    models.ResponseAudioTranscriptDoneMessage |
    models.ItemInputAudioTranscriptionDeltaMessage |
    models.ItemInputAudioTranscriptionCompletedMessage |
    models.ResponseOutputItemDoneMessage |
    models.ResponseDoneMessage |
    models.UnknownServerMessage
)
MessageType = Union[UserMessageType, ServerMessageType]

# --- Message Factories ---
# The dictionaries now map strings to the imported model classes.
USER_MESSAGE_CLASSES: dict[str, Type[models.ClientMessageBase]] = {
    "input_audio_buffer.append": models.InputAudioBufferAppendMessage,
}
SERVER_MESSAGE_CLASSES: dict[str, Type[models.ServerMessageBase]] = {
    "input_audio_buffer.speech_started": models.InputAudioBufferSpeechStartedMessage,
    "input_audio_buffer.speech_stopped": models.InputAudioBufferSpeechStoppedMessage,
    "response.text.delta": models.ResponseTextDeltaMessage,
    "response.text.done": models.ResponseTextDoneMessage,
    "response.function_call_arguments.delta": models.ResponseFunctionCallArgumentsDeltaMessage,
    "response.function_call_arguments.done": models.ResponseFunctionCallArgumentsDoneMessage,
    "response.audio.delta": models.ResponseAudioDeltaMessage,
    "response.audio.done": models.ResponseAudioDoneMessage,
    "response.audio_transcript.delta": models.ResponseAudioTranscriptDeltaMessage,
    "response.audio_transcript.done": models.ResponseAudioTranscriptDoneMessage,
    "conversation.item.input_audio_transcription.delta": models.ItemInputAudioTranscriptionDeltaMessage,
    "conversation.item.input_audio_transcription.completed": models.ItemInputAudioTranscriptionCompletedMessage,
    "response.output_item.done": models.ResponseOutputItemDoneMessage,
    "response.done": models.ResponseDoneMessage,
}

def create_user_message_from_dict(data: dict) -> models.ClientMessageBase:
    event_type = data.get("type")

    if not event_type:
        return models.UnknownClientMessage(**data)

    message_class = USER_MESSAGE_CLASSES.get(event_type)
    if message_class:
        return message_class.model_validate(data)

    return models.UnknownClientMessage(**data)

def create_server_message_from_dict(data: dict) -> models.ServerMessageBase:
    event_type = data.get("type")

    if not event_type:
        return models.UnknownServerMessage(**data)

    message_class = SERVER_MESSAGE_CLASSES.get(event_type)
    if message_class:
        return message_class.model_validate(data)

    return models.UnknownServerMessage(**data)

T = TypeVar("T", bound=Union[str, bytes])
class BaseItem(Generic[T]):
    is_complete: bool = False
    val: T

    def set_completed(self, val: Optional[T] = None):
        if val:
            self.val = val
        self.is_complete = True

    def has_content(self):
        return len(self.val) > 0

    @abstractmethod
    def as_content(self) -> dict:
        ...


class AudioItem(BaseItem[bytes]):
    val: bytes = b""

    def append(self, val: str | bytes):
        if isinstance(val, str):
            val = base64.b64decode(val)
        self.val += val

    def as_content(self) -> dict:
        content = Content.from_bytes(pcm_to_wav(self.val), extension="wav")
        return {
            "type": "audio",
            "audio": {
                "data": content,
                "format": "wav"
            }
        }

class TextItem(BaseItem[str]):
    val: str = ""

    def append(self, val: str):
        self.val += val

    def as_content(self) -> dict:
        return {
            "type": "text",
            "text": self.val
        }

class FunctionItem(BaseItem[str]):
    text: str = ""

    def append(self, val: str):
        self.val += val

    def as_content(self) -> dict:
        return {
            "type": "text",
            "text": self.val
        }

Item = FunctionItem | TextItem | AudioItem

class ItemState:
    item_id = str
    last_item_id: Optional[str] = None
    function_args: Optional[FunctionItem] = None
    text: Optional[TextItem] = None
    transcript: Optional[TextItem] = None
    audio: Optional[AudioItem] = None

    """Represents the state of a single item, separating input and output data."""
    def __init__(self, item_id: str):
        self.item_id = item_id

    def add_item_content(self, item_type: Literal["function_args", "text", "transcript", "audio"]):
        if item_type == "function_args":
            self.function_args = FunctionItem()
        elif item_type == "text":
            self.text = TextItem()
        elif item_type == "transcript":
            self.transcript = TextItem()
        elif item_type == "audio":
            self.audio = AudioItem()

    def is_complete(self):
        function_complete = not self.function_args or self.function_args.is_complete
        text_complete = not self.text or self.text.is_complete
        transcript_complete = not self.transcript or self.transcript.is_complete
        audio_complete = not self.audio or self.audio.is_complete
        return function_complete and text_complete and transcript_complete and audio_complete


class FunctionCall:
    name: str
    arguments: str

class ToolCall:
    type: Literal["function"]
    id: str
    function: FunctionCall

class ToolCallResultMessage:
    role: Literal["tool"]
    content: str
    tool_call_id: str
    name: str

class BasicChatMessage:
    role: Literal["assistant", "user", "system"]
    content: Optional[list[BaseItem]]
    tool_calls: list[ToolCall]


ChatMessage = ToolCallResultMessage | BasicChatMessage

class ConversationManager:
    """Manages conversation state by processing both user and server events."""
    def __init__(self):
        self._items: dict[str, ItemState] = {}
        self._lock = asyncio.Lock()
        self._current_user_speech_item_id: str | None = None

    async def get_item(self, item_id: str) -> ItemState:
        async with self._lock:
            if item_id not in self._items:
                self._items[item_id] = ItemState(item_id=item_id)
            return self._items[item_id]

    async def process_event(self, event: MessageType):
        if isinstance(event, models.InputAudioBufferSpeechStartedMessage):
            self._current_user_speech_item_id = event.item_id
            item = await self.get_item(event.item_id) # Ensure item state exists
            item.audio = AudioItem() # clear existing audio
            return

        elif isinstance(event, models.ItemCreatedMessage):
            item_id = event.item.id
            if not item_id:
                return

            item = self.get_item(item_id)
            event.previous_item_id

        elif isinstance(event, models.InputAudioBufferSpeechStoppedMessage):
            if self._current_user_speech_item_id == event.item_id:
                self._current_user_speech_item_id = None
            return

        elif isinstance(event, models.InputAudioBufferAppendMessage):
            if self._current_user_speech_item_id:
                item = await self.get_item(self._current_user_speech_item_id)
                if not item.audio:
                    # Just return if we haven't gotten 'speech started' yet
                    return
                try:
                    item.audio.append(event.audio)
                except (binascii.Error, TypeError) as e:
                    print(f"Warning: Could not decode user audio. Error: {e}")
            return

        elif isinstance(event, models.ResponseDoneMessage):
            # Marks completion of output
            create_turn(event, self.get_all_items())
            return

        elif isinstance(event, models.ResponseOutputItemDoneMessage):
            return

        elif isinstance(event, models.UnknownClientMessage):
            return

        elif isinstance(event, models.UnknownServerMessage):
            return

        elif not hasattr(event, "item_id") or not getattr(event, "item_id"):
            return

        item = await self.get_item(event.item_id)

        if isinstance(event, models.ResponseTextDeltaMessage):
            if not item.text:
                item.text = TextItem()
            item.text.append(event.delta)

        elif isinstance(event, models.ResponseFunctionCallArgumentsDeltaMessage):
            if not item.function_args:
                item.function_args = FunctionItem()
            item.function_args.append(event.delta)

        elif isinstance(event, (models.ResponseAudioTranscriptDeltaMessage, models.ItemInputAudioTranscriptionDeltaMessage)):
            if not item.transcript:
                item.transcript = TextItem()
            item.transcript.append(event.delta)

        elif isinstance(event, models.ResponseAudioDeltaMessage):
            if not item.audio:
                item.audio = AudioItem()

            try:
                item.audio.append(event.delta)
            except (binascii.Error, TypeError) as e:
                print(f"Warning: Could not decode server audio for item {event.item_id}. Error: {e}")

        elif isinstance(event, models.ResponseTextDoneMessage):
            if not item.text:
                raise RuntimeError("Tried to complete untracked item")
            item.text.set_completed(event.text)

        elif isinstance(event, models.ResponseFunctionCallArgumentsDoneMessage):
            if not item.function_args:
                raise RuntimeError("Tried to complete untracked item")
            item.function_args.set_completed(event.arguments)

        elif isinstance(event, (models.ResponseAudioTranscriptDoneMessage, models.ItemInputAudioTranscriptionCompletedMessage)):
            if not item.transcript:
                raise RuntimeError("Tried to complete untracked item")
            item.transcript.set_completed(event.transcript)

    def get_all_items(self) -> dict[str, ItemState]:
        return self._items.copy()


def create_turn(event: models.ResponseDoneMessage, items: dict[str, ItemState]):
    outputs = {}
    # Build choices array from assistant response
    choices = []
    outputs = event.response.output
    if len(outputs) == 0:
        raise ValueError("recieved empty outputs")
    output_item = outputs[0]

    item_id = output_item.id
    if not item_id:
        raise ValueError("Output has no item id")
    item = items.get(item_id)

    if not item:
        raise ValueError(f"Failed to get item - {item_id}")
    last_item_id = item.last_item_id

    input_items = []
    while(last_item_id != None):



    if items.get(event.response.id:
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
