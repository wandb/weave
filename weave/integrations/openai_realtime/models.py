from __future__ import annotations

import logging
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, AliasChoices, BaseModel, Field
from pydantic_core import ValidationError

logger = logging.getLogger(__name__)

"""
Heavily inspired/originally based on this file from Azure:
https://raw.githubusercontent.com/Azure-Samples/aoai-realtime-audio-sdk/refs/heads/main/python/rtclient/models.py

Note that this file defines types for the OpenAI beta API and does not support the GA release

Modifications for ease of development were made to:
    1. Specify when IDs are definitely present or not instead of making them optional
    2. Separating what was originally the same class when it has or lacks fields depending on the source (client or server)


Ideally we would move to the types in the openai sdk
beta - https://github.com/openai/openai-python/tree/main/src/openai/types/beta/realtime
GA - https://github.com/openai/openai-python/tree/main/src/openai/types/realtime

Unfortunately model validation for incoming/outgoing messages for perfectly functional clients continually fails for these types
The official sdk provides wrappers for interacting with the websockets that likely validate and modify missing fields from the user
It's likely that the types will stabilize or we can wrap them in some way to be less strict, but for now this file is necessary

This will get a second pass when support for the GA version of realtime is added and be deleted in the future.
"""


def is_conv_id(id: str) -> str:
    """ID for a conversation such as "conv_C9IkmOhAf8dw7uQyToBFI"."""
    if id.startswith("conv_"):
        return id
    raise ValueError(f"ID {id} is not a conversation ID")


def is_call_id(id: str) -> str:
    """ID for a function call such as call_mkaZeOUzwGFi8Xap."""
    if id.startswith("call_"):
        return id
    raise ValueError(f"ID {id} is not a call ID")


def is_sess_id(id: str) -> str:
    """ID for a session such as sess_mkaZeOUzwGFi8Xap."""
    if id.startswith("sess_"):
        return id
    raise ValueError(f"ID {id} is not a session ID")


def is_event_id(id: str) -> str:
    """ID for an event such as event_mkaZeOUzwGFi8Xap."""
    if id.startswith("event_"):
        return id
    raise ValueError(f"ID {id} is not an event ID")


def is_item_id(id: str) -> str:
    """ID for an item such as item_mkaZeOUzwGFi8Xap."""
    if id.startswith("item_"):
        return id
    raise ValueError(f"ID {id} is not an item ID")


def is_resp_id(id: str) -> str:
    """ID for an response such as resp_mkaZeOUzwGFi8Xap."""
    if id.startswith("resp_"):
        return id
    raise ValueError(f"ID {id} is not a response ID")


SessionID = Annotated[str, AfterValidator(is_sess_id)]
EventID = Annotated[str, AfterValidator(is_event_id)]
ItemID = Annotated[str, AfterValidator(is_item_id)]
ResponseID = Annotated[str, AfterValidator(is_resp_id)]
CallID = Annotated[str, AfterValidator(is_call_id)]
ConversationID = Annotated[str, AfterValidator(is_conv_id)]

# https://platform.openai.com/docs/api-reference/realtime-client-events/session/update
Voice = Literal[
    "alloy",
    "ash",
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse",
    "marin",
    "cedar",
]
AudioFormat = Literal["pcm16", "g711-ulaw", "g711-alaw"]
Modality = Literal["text", "audio"]


class NoTurnDetection(BaseModel):
    type: Literal["none"] = "none"


class ServerVAD(BaseModel):
    type: Literal["server_vad"] = "server_vad"
    threshold: Annotated[float, Field(strict=True, ge=0.0, le=1.0)] | None = None
    prefix_padding_ms: int | None = None
    silence_duration_ms: int | None = None


TurnDetection = Annotated[NoTurnDetection | ServerVAD, Field(discriminator="type")]


class FunctionToolChoice(BaseModel):
    type: Literal["function"] = "function"
    function: str


ToolChoice = Literal["auto", "none", "required"] | FunctionToolChoice

MessageRole = Literal["system", "assistant", "user"]


class InputAudioTranscription(BaseModel):
    model: Literal["whisper-1"]


class ClientMessageBase(BaseModel):
    event_id: EventID | None = None


Temperature = Annotated[float, Field(strict=True, ge=0.6, le=1.2)]
ToolsDefinition = list[Any]


class SessionUpdateParams(BaseModel):
    model: str | None = None
    modalities: set[Modality] | None = None
    voice: Voice | None = None
    instructions: str | None = None
    input_audio_format: AudioFormat | None = None
    output_audio_format: AudioFormat | None = None
    input_audio_transcription: InputAudioTranscription | None = None
    turn_detection: TurnDetection | None = None
    tools: ToolsDefinition | None = None
    tool_choice: ToolChoice | None = None
    temperature: Temperature | None = None
    max_response_output_tokens: int | None = None


class SessionUpdateMessage(ClientMessageBase):
    """Update the session configuration."""

    type: Literal["session.update"] = "session.update"
    session: SessionUpdateParams


class InputAudioBufferAppendMessage(ClientMessageBase):
    """Append audio data to the user audio buffer, this should be in the format specified by
    input_audio_format in the session config.
    """

    type: Literal["input_audio_buffer.append"] = "input_audio_buffer.append"
    audio: str


class InputAudioBufferCommitMessage(ClientMessageBase):
    """Commit the pending user audio buffer, which creates a user message item with the audio content
    and clears the buffer.
    """

    type: Literal["input_audio_buffer.commit"] = "input_audio_buffer.commit"


class InputAudioBufferClearMessage(ClientMessageBase):
    """Clear the user audio buffer, discarding any pending audio data."""

    type: Literal["input_audio_buffer.clear"] = "input_audio_buffer.clear"


MessageItemType = Literal["message"]


class InputTextContentPart(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class InputAudioContentPart(BaseModel):
    type: Literal["input_audio"] = "input_audio"
    # Some server events (e.g., conversation.item.created) may omit the raw
    # audio payload and only include a transcript placeholder. Make audio
    # optional to be tolerant of such cases during replays and future API
    # changes.
    audio: str | None = None
    transcript: str | None = None


class OutputTextContentPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


SystemContentPart = InputTextContentPart
UserContentPart = Annotated[
    InputTextContentPart | InputAudioContentPart, Field(discriminator="type")
]
AssistantContentPart = OutputTextContentPart

ItemParamStatus = Literal["completed", "incomplete", "in_progress"]


# Base classes for items - common attributes
class BaseMessageItem(BaseModel):
    """Base class for message items with common attributes"""

    type: MessageItemType = "message"
    content: list[Any]  # Will be overridden in subclasses
    status: ItemParamStatus | None = None


class BaseFunctionCallItem(BaseModel):
    """Base class for function call items with common attributes"""

    type: Literal["function_call"] = "function_call"
    name: str
    call_id: CallID
    arguments: str
    status: ItemParamStatus | None = None


class BaseFunctionCallOutputItem(BaseModel):
    """Base class for function call output items with common attributes"""

    type: Literal["function_call_output"] = "function_call_output"
    call_id: CallID
    output: str
    status: ItemParamStatus | None = None


# Client-side items (no IDs)
class ClientSystemMessageItem(BaseMessageItem):
    """System message item as sent by client"""

    role: Literal["system"] = "system"
    content: list[SystemContentPart]


class ClientUserMessageItem(BaseMessageItem):
    """User message item as sent by client"""

    role: Literal["user"] = "user"
    content: list[UserContentPart]


class ClientAssistantMessageItem(BaseMessageItem):
    """Assistant message item as sent by client"""

    role: Literal["assistant"] = "assistant"
    content: list[AssistantContentPart]


class ClientFunctionCallItem(BaseFunctionCallItem):
    """Function call item as sent by client"""

    pass


class ClientFunctionCallOutputItem(BaseFunctionCallOutputItem):
    """Function call output item as sent by client"""

    pass


# Server-side items (with IDs and object field)
class ServerSystemMessageItem(BaseMessageItem):
    """System message item as sent by server"""

    id: ItemID
    object: Literal["realtime.item"] = "realtime.item"
    role: Literal["system"] = "system"
    content: list[SystemContentPart]


class ServerUserMessageItem(BaseMessageItem):
    """User message item as sent by server"""

    id: ItemID
    object: Literal["realtime.item"] = "realtime.item"
    role: Literal["user"] = "user"
    content: list[UserContentPart]


class ServerAssistantMessageItem(BaseMessageItem):
    """Assistant message item as sent by server"""

    id: ItemID
    object: Literal["realtime.item"] = "realtime.item"
    role: Literal["assistant"] = "assistant"
    content: list[AssistantContentPart]


class ServerFunctionCallItem(BaseFunctionCallItem):
    """Function call item as sent by server"""

    id: ItemID
    object: Literal["realtime.item"] = "realtime.item"


class ServerFunctionCallOutputItem(BaseFunctionCallOutputItem):
    """Function call output item as sent by server"""

    id: ItemID
    object: Literal["realtime.item"] = "realtime.item"


# Union types for client and server items
ClientMessageItem = Annotated[
    ClientSystemMessageItem | ClientUserMessageItem | ClientAssistantMessageItem,
    Field(discriminator="role"),
]
ServerMessageItem = Annotated[
    ServerSystemMessageItem | ServerUserMessageItem | ServerAssistantMessageItem,
    Field(discriminator="role"),
]
ClientItem = Annotated[
    ClientMessageItem | ClientFunctionCallItem | ClientFunctionCallOutputItem,
    Field(discriminator="type"),
]

ServerItem = Annotated[
    ServerMessageItem | ServerFunctionCallItem | ServerFunctionCallOutputItem,
    Field(discriminator="type"),
]


class ItemCreateMessage(ClientMessageBase):
    type: Literal["conversation.item.create"] = "conversation.item.create"
    previous_item_id: ItemID | None = None
    item: ClientItem


class ItemTruncateMessage(ClientMessageBase):
    type: Literal["conversation.item.truncate"] = "conversation.item.truncate"
    item_id: ItemID
    content_index: int
    audio_end_ms: int


class ItemDeleteMessage(ClientMessageBase):
    type: Literal["conversation.item.delete"] = "conversation.item.delete"
    item_id: ItemID


class ResponseCreateParams(BaseModel):
    commit: bool = True
    cancel_previous: bool = True
    append_input_items: list[ClientItem] | None = None
    input_items: list[ClientItem] | None = None
    instructions: str | None = None
    modalities: set[Modality] | None = None
    voice: Voice | None = None
    temperature: Temperature | None = None
    max_output_tokens: int | None = None
    tools: ToolsDefinition | None = None
    tool_choice: ToolChoice | None = None
    output_audio_format: AudioFormat | None = None


class ResponseCreateMessage(ClientMessageBase):
    """Trigger model inference to generate a model turn."""

    type: Literal["response.create"] = "response.create"
    response: ResponseCreateParams | None = None


class ResponseCancelMessage(ClientMessageBase):
    type: Literal["response.cancel"] = "response.cancel"


class RealtimeError(BaseModel):
    message: str
    type: str | None = None
    code: str | None = None
    param: str | None = None
    event_id: EventID | None = None


class ServerMessageBase(BaseModel):
    event_id: EventID


class ErrorMessage(ServerMessageBase):
    type: Literal["error"] = "error"
    error: RealtimeError


class UnknownMessage(BaseModel):
    type: str = "unknown"


class UnknownClientMessage(ClientMessageBase, UnknownMessage): ...


class UnknownServerMessage(ServerMessageBase, UnknownMessage): ...


class Session(BaseModel):
    id: SessionID | None = None
    model: str | None = None
    modalities: set[Modality] | None = None
    instructions: str | None = None
    voice: Voice | None = None
    input_audio_format: AudioFormat | None = None
    output_audio_format: AudioFormat | None = None
    input_audio_transcription: InputAudioTranscription | None
    turn_detection: TurnDetection | None = None
    tools: ToolsDefinition | None = None
    tool_choice: ToolChoice | None = None
    temperature: Temperature | None = None
    max_response_output_tokens: int | Literal["inf"] | None = None


class SessionCreatedMessage(ServerMessageBase):
    type: Literal["session.created"] = "session.created"
    session: Session


class SessionUpdatedMessage(ServerMessageBase):
    type: Literal["session.updated"] = "session.updated"
    session: Session


class InputAudioBufferCommittedMessage(ServerMessageBase):
    """Signals the server has received and processed the audio buffer."""

    type: Literal["input_audio_buffer.committed"] = "input_audio_buffer.committed"
    previous_item_id: ItemID | None  # Fixed type: was Optional[str]
    item_id: ItemID


class InputAudioBufferClearedMessage(ServerMessageBase):
    """Signals the server has cleared the audio buffer."""

    type: Literal["input_audio_buffer.cleared"] = "input_audio_buffer.cleared"


class InputAudioBufferSpeechStartedMessage(ServerMessageBase):
    """If the server VAD is enabled, this event is sent when speech is detected in the user audio buffer.
    It tells you where in the audio stream (in milliseconds) the speech started, plus an item_id
    which will be used in the corresponding speech_stopped event and the item created in the conversation
    when speech stops.
    """

    type: Literal["input_audio_buffer.speech_started"] = (
        "input_audio_buffer.speech_started"
    )
    audio_start_ms: int
    item_id: ItemID


class InputAudioBufferSpeechStoppedMessage(ServerMessageBase):
    """If the server VAD is enabled, this event is sent when speech stops in the user audio buffer.
    It tells you where in the audio stream (in milliseconds) the speech stopped, plus an item_id
    which will be used in the corresponding speech_started event and the item created in the conversation
    when speech starts.
    """

    type: Literal["input_audio_buffer.speech_stopped"] = (
        "input_audio_buffer.speech_stopped"
    )
    audio_end_ms: int
    item_id: ItemID


ResponseItemStatus = Literal["in_progress", "completed", "incomplete"]


class ResponseItemInputTextContentPart(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class ResponseItemInputAudioContentPart(BaseModel):
    type: Literal["input_audio"] = "input_audio"
    transcript: str | None


class ResponseItemTextContentPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ResponseItemAudioContentPart(BaseModel):
    type: Literal["audio"] = "audio"
    audio: str | None = None
    transcript: str | None = None


ResponseItemContentPart = Annotated[
    ResponseItemInputTextContentPart
    | ResponseItemInputAudioContentPart
    | ResponseItemTextContentPart
    | ResponseItemAudioContentPart,
    Field(discriminator="type"),
]


class ResponseItemBase(BaseModel):
    """Base class for response items - these are always from server so always have IDs"""

    id: ItemID  # Always required for server responses
    status: ResponseItemStatus  # Always has a status


class ResponseMessageItem(ResponseItemBase):
    type: MessageItemType = "message"
    role: MessageRole
    content: list[ResponseItemContentPart]


class ResponseFunctionCallItem(ResponseItemBase):
    type: Literal["function_call"] = "function_call"
    name: str
    call_id: CallID
    arguments: str


class ResponseFunctionCallOutputItem(ResponseItemBase):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: CallID
    output: str


ResponseItem = Annotated[
    ResponseMessageItem | ResponseFunctionCallItem | ResponseFunctionCallOutputItem,
    Field(discriminator="type"),
]


class ItemCreatedMessage(ServerMessageBase):
    type: Literal["conversation.item.created"] = "conversation.item.created"
    previous_item_id: ItemID | None
    item: ServerItem


class ItemTruncatedMessage(ServerMessageBase):
    type: Literal["conversation.item.truncated"] = "conversation.item.truncated"
    item_id: ItemID
    content_index: int
    audio_end_ms: int


class ItemDeletedMessage(ServerMessageBase):
    type: Literal["conversation.item.deleted"] = "conversation.item.deleted"
    item_id: ItemID


class ItemInputAudioTranscriptionCompletedMessage(ServerMessageBase):
    type: Literal["conversation.item.input_audio_transcription.completed"] = (
        "conversation.item.input_audio_transcription.completed"
    )
    item_id: ItemID
    content_index: int
    transcript: str


class ItemInputAudioTranscriptionFailedMessage(ServerMessageBase):
    type: Literal["conversation.item.input_audio_transcription.failed"] = (
        "conversation.item.input_audio_transcription.failed"
    )
    item_id: ItemID
    content_index: int
    error: RealtimeError


class ItemInputAudioTranscriptionDeltaMessage(ServerMessageBase):
    type: Literal["conversation.item.input_audio_transcription.delta"] = (
        "conversation.item.input_audio_transcription.delta"
    )
    item_id: ItemID
    content_index: int
    delta: str


ResponseStatus = Literal[
    "in_progress", "completed", "cancelled", "incomplete", "failed"
]


class ResponseCancelledDetails(BaseModel):
    type: Literal["cancelled"] = "cancelled"
    reason: Literal["turn_detected", "client_cancelled"]


class ResponseIncompleteDetails(BaseModel):
    type: Literal["incomplete"] = "incomplete"
    reason: Literal["max_output_tokens", "content_filter"]


class ResponseFailedDetails(BaseModel):
    type: Literal["failed"] = "failed"
    error: Any


ResponseStatusDetails = Annotated[
    ResponseCancelledDetails | ResponseIncompleteDetails | ResponseFailedDetails,
    Field(discriminator="type"),
]


class TokenDetails(BaseModel):
    text_tokens: int
    audio_tokens: int
    image_tokens: int | None = 0


class InputTokenDetails(TokenDetails):
    cached_tokens: int
    cached_tokens_details: TokenDetails | None


class Usage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int
    input_token_details: InputTokenDetails | None
    output_token_details: TokenDetails | None


class Response(BaseModel):
    id: ResponseID  # Should be ResponseID, not str
    status: ResponseStatus
    status_details: ResponseStatusDetails | None
    output: list[ResponseItem]
    usage: Usage | None
    conversation_id: ConversationID | None


class ResponseCreatedMessage(ServerMessageBase):
    type: Literal["response.created"] = "response.created"
    response: Response


class ResponseDoneMessage(ServerMessageBase):
    type: Literal["response.done"] = "response.done"
    response: Response


class ResponseOutputItemAddedMessage(ServerMessageBase):
    type: Literal["response.output_item.added"] = "response.output_item.added"
    response_id: ResponseID
    output_index: int
    item: ResponseItem


class ResponseOutputItemDoneMessage(ServerMessageBase):
    type: Literal["response.output_item.done"] = "response.output_item.done"
    response_id: ResponseID
    output_index: int
    item: ResponseItem


class ResponseContentPartAddedMessage(ServerMessageBase):
    type: Literal["response.content_part.added"] = "response.content_part.added"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    part: Annotated[
        ResponseItemContentPart,
        Field(alias="part", validation_alias=AliasChoices("part", "content")),
    ]  # TODO: this alias won't be needed when AOAI and OAI are in sync.


class ResponseContentPartDoneMessage(ServerMessageBase):
    type: Literal["response.content_part.done"] = "response.content_part.done"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    part: Annotated[
        ResponseItemContentPart,
        Field(alias="part", validation_alias=AliasChoices("part", "content")),
    ]  # TODO: this alias won't be needed when AOAI and OAI are in sync.


class ResponseTextDeltaMessage(ServerMessageBase):
    type: Literal["response.text.delta"] = "response.text.delta"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    delta: str


class ResponseTextDoneMessage(ServerMessageBase):
    type: Literal["response.text.done"] = "response.text.done"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    text: str


class ResponseAudioTranscriptDeltaMessage(ServerMessageBase):
    type: Literal["response.audio_transcript.delta"] = "response.audio_transcript.delta"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    delta: str


class ResponseAudioTranscriptDoneMessage(ServerMessageBase):
    type: Literal["response.audio_transcript.done"] = "response.audio_transcript.done"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    transcript: str


class ResponseAudioDeltaMessage(ServerMessageBase):
    type: Literal["response.audio.delta"] = "response.audio.delta"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int
    delta: str


class ResponseAudioDoneMessage(ServerMessageBase):
    type: Literal["response.audio.done"] = "response.audio.done"
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    content_index: int


class ResponseFunctionCallArgumentsDeltaMessage(ServerMessageBase):
    type: Literal["response.function_call_arguments.delta"] = (
        "response.function_call_arguments.delta"
    )
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    call_id: CallID
    delta: str


class ResponseFunctionCallArgumentsDoneMessage(ServerMessageBase):
    type: Literal["response.function_call_arguments.done"] = (
        "response.function_call_arguments.done"
    )
    response_id: ResponseID
    item_id: ItemID
    output_index: int
    call_id: CallID
    name: str
    arguments: str


class RateLimits(BaseModel):
    name: str
    limit: int
    remaining: int
    reset_seconds: float


class RateLimitsUpdatedMessage(ServerMessageBase):
    type: Literal["rate_limits.updated"] = "rate_limits.updated"
    rate_limits: list[RateLimits]


UserMessageType = Annotated[
    SessionUpdateMessage
    | InputAudioBufferAppendMessage
    | InputAudioBufferCommitMessage
    | InputAudioBufferClearMessage
    | ItemCreateMessage
    | ItemTruncateMessage
    | ItemDeleteMessage
    | ResponseCreateMessage
    | ResponseCancelMessage
    | UnknownClientMessage,
    Field(discriminator="type"),
]

ServerMessageType = Annotated[
    ErrorMessage
    | SessionCreatedMessage
    | SessionUpdatedMessage
    | InputAudioBufferCommittedMessage
    | InputAudioBufferClearedMessage
    | InputAudioBufferSpeechStartedMessage
    | InputAudioBufferSpeechStoppedMessage
    | ItemCreatedMessage
    | ItemTruncatedMessage
    | ItemDeletedMessage
    | ItemInputAudioTranscriptionCompletedMessage
    | ItemInputAudioTranscriptionFailedMessage
    | ItemInputAudioTranscriptionDeltaMessage
    | ResponseCreatedMessage
    | ResponseDoneMessage
    | ResponseOutputItemAddedMessage
    | ResponseOutputItemDoneMessage
    | ResponseContentPartAddedMessage
    | ResponseContentPartDoneMessage
    | ResponseTextDeltaMessage
    | ResponseTextDoneMessage
    | ResponseAudioTranscriptDeltaMessage
    | ResponseAudioTranscriptDoneMessage
    | ResponseAudioDeltaMessage
    | ResponseAudioDoneMessage
    | ResponseFunctionCallArgumentsDeltaMessage
    | ResponseFunctionCallArgumentsDoneMessage
    | RateLimitsUpdatedMessage
    | UnknownServerMessage,
    Field(discriminator="type"),
]

# Dictionary mapping user message types to their respective classes.
USER_MESSAGE_CLASSES: dict[str, type[UserMessageType]] = {
    "session.update": SessionUpdateMessage,
    "input_audio_buffer.append": InputAudioBufferAppendMessage,
    "input_audio_buffer.commit": InputAudioBufferCommitMessage,
    "input_audio_buffer.clear": InputAudioBufferClearMessage,
    "conversation.item.create": ItemCreateMessage,
    "conversation.item.truncate": ItemTruncateMessage,
    "conversation.item.delete": ItemDeleteMessage,
    "response.create": ResponseCreateMessage,
    "response.cancel": ResponseCancelMessage,
}

# Dictionary mapping server message types to their respective classes.
# The type hint is changed to Type[ServerMessageType] for the same reason.
SERVER_MESSAGE_CLASSES: dict[str, type[ServerMessageType]] = {
    "error": ErrorMessage,
    "session.created": SessionCreatedMessage,
    "session.updated": SessionUpdatedMessage,
    "input_audio_buffer.committed": InputAudioBufferCommittedMessage,
    "input_audio_buffer.cleared": InputAudioBufferClearedMessage,
    "input_audio_buffer.speech_started": InputAudioBufferSpeechStartedMessage,
    "input_audio_buffer.speech_stopped": InputAudioBufferSpeechStoppedMessage,
    "conversation.item.created": ItemCreatedMessage,
    "conversation.item.truncated": ItemTruncatedMessage,
    "conversation.item.deleted": ItemDeletedMessage,
    "conversation.item.input_audio_transcription.completed": ItemInputAudioTranscriptionCompletedMessage,
    "conversation.item.input_audio_transcription.failed": ItemInputAudioTranscriptionFailedMessage,
    "conversation.item.input_audio_transcription.delta": ItemInputAudioTranscriptionDeltaMessage,
    "response.created": ResponseCreatedMessage,
    "response.done": ResponseDoneMessage,
    "response.output_item.added": ResponseOutputItemAddedMessage,
    "response.output_item.done": ResponseOutputItemDoneMessage,
    "response.content_part.added": ResponseContentPartAddedMessage,
    "response.content_part.done": ResponseContentPartDoneMessage,
    "response.text.delta": ResponseTextDeltaMessage,
    "response.text.done": ResponseTextDoneMessage,
    "response.audio_transcript.delta": ResponseAudioTranscriptDeltaMessage,
    "response.audio_transcript.done": ResponseAudioTranscriptDoneMessage,
    "response.audio.delta": ResponseAudioDeltaMessage,
    "response.audio.done": ResponseAudioDoneMessage,
    "response.function_call_arguments.delta": ResponseFunctionCallArgumentsDeltaMessage,
    "response.function_call_arguments.done": ResponseFunctionCallArgumentsDoneMessage,
    "rate_limits.updated": RateLimitsUpdatedMessage,
}

MessageType = UserMessageType | ServerMessageType


def create_user_message_from_dict(data: dict) -> UserMessageType | None:
    """Create a user message object from a dictionary based on its 'type'."""
    event_type = data.get("type")
    if not event_type:
        return None
    # Use .get() to look up the class, providing a default if the key is not found.
    cls = USER_MESSAGE_CLASSES.get(event_type, None)

    if not cls:
        return None

    try:
        return cls(**data)
    except ValidationError as e:
        logger.debug(
            f"Failed to construct message for type {event_type} with error - {e}"
        )

    return None


def create_server_message_from_dict(data: dict) -> ServerMessageType | None:
    event_type = data.get("type")
    if not event_type:
        return None
    # Use .get() to look up the class, providing a default if the key is not found.
    cls = SERVER_MESSAGE_CLASSES.get(event_type, None)

    if not cls:
        return None

    try:
        return cls(**data)
    except ValidationError as e:
        logger.debug(
            f"Failed to construct message for type {event_type} with error - {e}"
        )

    return None


def create_message_from_dict(data: dict) -> MessageType | None:
    """Create a message object from a dictionary based on its 'type'."""
    event_type = data.get("type") or ""
    if event_type in USER_MESSAGE_CLASSES.keys():
        return create_user_message_from_dict(data)

    elif event_type in SERVER_MESSAGE_CLASSES.keys():
        return create_server_message_from_dict(data)

    logger.warning(f"Unknown message type - {event_type}")
    return None
