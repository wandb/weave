# Credit to Microsoft for the original source: https://github.com/Azure-Samples/aoai-realtime-audio-sdk/blob/main/python/rtclient/models.py
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

from typing import Annotated, Any, Literal, Optional, Union, Type

from pydantic import AliasChoices, BaseModel, Field

Voice = Literal["alloy", "shimmer", "echo"]
AudioFormat = Literal["pcm16", "g711-ulaw", "g711-alaw"]
Modality = Literal["text", "audio"]


class NoTurnDetection(BaseModel):
    type: Literal["none"] = "none"


class ServerVAD(BaseModel):
    type: Literal["server_vad"] = "server_vad"
    threshold: Optional[Annotated[float, Field(strict=True, ge=0.0, le=1.0)]] = None
    prefix_padding_ms: Optional[int] = None
    silence_duration_ms: Optional[int] = None


TurnDetection = Annotated[Union[NoTurnDetection, ServerVAD], Field(discriminator="type")]


class FunctionToolChoice(BaseModel):
    type: Literal["function"] = "function"
    function: str


ToolChoice = Literal["auto", "none", "required"] | FunctionToolChoice

MessageRole = Literal["system", "assistant", "user"]


class InputAudioTranscription(BaseModel):
    model: Literal["whisper-1"]


class ClientMessageBase(BaseModel):
    event_id: Optional[str] = None


Temperature = Annotated[float, Field(strict=True, ge=0.6, le=1.2)]
ToolsDefinition = list[Any]


class SessionUpdateParams(BaseModel):
    model: Optional[str] = None
    modalities: Optional[set[Modality]] = None
    voice: Optional[Voice] = None
    instructions: Optional[str] = None
    input_audio_format: Optional[AudioFormat] = None
    output_audio_format: Optional[AudioFormat] = None
    input_audio_transcription: Optional[InputAudioTranscription] = None
    turn_detection: Optional[TurnDetection] = None
    tools: Optional[ToolsDefinition] = None
    tool_choice: Optional[ToolChoice] = None
    temperature: Optional[Temperature] = None
    max_response_output_tokens: Optional[int] = None


class SessionUpdateMessage(ClientMessageBase):
    """
    Update the session configuration.
    """

    type: Literal["session.update"] = "session.update"
    session: SessionUpdateParams


class InputAudioBufferAppendMessage(ClientMessageBase):
    """
    Append audio data to the user audio buffer, this should be in the format specified by
    input_audio_format in the session config.
    """

    type: Literal["input_audio_buffer.append"] = "input_audio_buffer.append"
    audio: str


class InputAudioBufferCommitMessage(ClientMessageBase):
    """
    Commit the pending user audio buffer, which creates a user message item with the audio content
    and clears the buffer.
    """

    type: Literal["input_audio_buffer.commit"] = "input_audio_buffer.commit"


class InputAudioBufferClearMessage(ClientMessageBase):
    """
    Clear the user audio buffer, discarding any pending audio data.
    """

    type: Literal["input_audio_buffer.clear"] = "input_audio_buffer.clear"


MessageItemType = Literal["message"]


class InputTextContentPart(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class InputAudioContentPart(BaseModel):
    type: Literal["input_audio"] = "input_audio"
    audio: str
    transcript: Optional[str] = None


class OutputTextContentPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


SystemContentPart = InputTextContentPart
UserContentPart = Union[Annotated[Union[InputTextContentPart, InputAudioContentPart], Field(discriminator="type")]]
AssistantContentPart = OutputTextContentPart

ItemParamStatus = Literal["completed", "incomplete"]


class SystemMessageItem(BaseModel):
    type: MessageItemType = "message"
    role: Literal["system"] = "system"
    id: Optional[str] = None
    content: list[SystemContentPart]
    status: Optional[ItemParamStatus] = None


class UserMessageItem(BaseModel):
    type: MessageItemType = "message"
    role: Literal["user"] = "user"
    id: Optional[str] = None
    content: list[UserContentPart]
    status: Optional[ItemParamStatus] = None


class AssistantMessageItem(BaseModel):
    type: MessageItemType = "message"
    role: Literal["assistant"] = "assistant"
    id: Optional[str] = None
    content: list[AssistantContentPart]
    status: Optional[ItemParamStatus] = None


MessageItem = Annotated[Union[SystemMessageItem, UserMessageItem, AssistantMessageItem], Field(discriminator="role")]


class FunctionCallItem(BaseModel):
    type: Literal["function_call"] = "function_call"
    id: Optional[str] = None
    name: str
    call_id: str
    arguments: str
    status: Optional[ItemParamStatus] = None


class FunctionCallOutputItem(BaseModel):
    type: Literal["function_call_output"] = "function_call_output"
    id: Optional[str] = None
    call_id: str
    output: str
    status: Optional[ItemParamStatus] = None


Item = Annotated[Union[MessageItem, FunctionCallItem, FunctionCallOutputItem], Field(discriminator="type")]


class ItemCreateMessage(ClientMessageBase):
    type: Literal["conversation.item.create"] = "conversation.item.create"
    previous_item_id: Optional[str] = None
    item: Item


class ItemTruncateMessage(ClientMessageBase):
    type: Literal["conversation.item.truncate"] = "conversation.item.truncate"
    item_id: str
    content_index: int
    audio_end_ms: int


class ItemDeleteMessage(ClientMessageBase):
    type: Literal["conversation.item.delete"] = "conversation.item.delete"
    item_id: str


class ResponseCreateParams(BaseModel):
    commit: bool = True
    cancel_previous: bool = True
    append_input_items: Optional[list[Item]] = None
    input_items: Optional[list[Item]] = None
    instructions: Optional[str] = None
    modalities: Optional[set[Modality]] = None
    voice: Optional[Voice] = None
    temperature: Optional[Temperature] = None
    max_output_tokens: Optional[int] = None
    tools: Optional[ToolsDefinition] = None
    tool_choice: Optional[ToolChoice] = None
    output_audio_format: Optional[AudioFormat] = None


class ResponseCreateMessage(ClientMessageBase):
    """
    Trigger model inference to generate a model turn.
    """

    type: Literal["response.create"] = "response.create"
    response: Optional[ResponseCreateParams] = None


class ResponseCancelMessage(ClientMessageBase):
    type: Literal["response.cancel"] = "response.cancel"


class RealtimeError(BaseModel):
    message: str
    type: Optional[str] = None
    code: Optional[str] = None
    param: Optional[str] = None
    event_id: Optional[str] = None


class ServerMessageBase(BaseModel):
    event_id: str


class ErrorMessage(ServerMessageBase):
    type: Literal["error"] = "error"
    error: RealtimeError

class UnknownMessage(BaseModel):
    type: str = "unknown"

class UnknownClientMessage(ClientMessageBase, UnknownMessage):
    ...

class UnknownServerMessage(ServerMessageBase, UnknownMessage):
    ...

class Session(BaseModel):
    id: str
    model: str
    modalities: set[Modality]
    instructions: str
    voice: Voice
    input_audio_format: AudioFormat
    output_audio_format: AudioFormat
    input_audio_transcription: Optional[InputAudioTranscription]
    turn_detection: TurnDetection
    tools: ToolsDefinition
    tool_choice: ToolChoice
    temperature: Temperature
    max_response_output_tokens: Optional[Union[int, Literal["inf"]]]


class SessionCreatedMessage(ServerMessageBase):
    type: Literal["session.created"] = "session.created"
    session: Session


class SessionUpdatedMessage(ServerMessageBase):
    type: Literal["session.updated"] = "session.updated"
    session: Session



class InputAudioBufferCommittedMessage(ServerMessageBase):
    """
    Signals the server has received and processed the audio buffer.
    """

    type: Literal["input_audio_buffer.committed"] = "input_audio_buffer.committed"
    previous_item_id: Optional[str]
    item_id: str


class InputAudioBufferClearedMessage(ServerMessageBase):
    """
    Signals the server has cleared the audio buffer.
    """

    type: Literal["input_audio_buffer.cleared"] = "input_audio_buffer.cleared"


class InputAudioBufferSpeechStartedMessage(ServerMessageBase):
    """
    If the server VAD is enabled, this event is sent when speech is detected in the user audio buffer.
    It tells you where in the audio stream (in milliseconds) the speech started, plus an item_id
    which will be used in the corresponding speech_stopped event and the item created in the conversation
    when speech stops.
    """

    type: Literal["input_audio_buffer.speech_started"] = "input_audio_buffer.speech_started"
    audio_start_ms: int
    item_id: str


class InputAudioBufferSpeechStoppedMessage(ServerMessageBase):
    """
    If the server VAD is enabled, this event is sent when speech stops in the user audio buffer.
    It tells you where in the audio stream (in milliseconds) the speech stopped, plus an item_id
    which will be used in the corresponding speech_started event and the item created in the conversation
    when speech starts.
    """

    type: Literal["input_audio_buffer.speech_stopped"] = "input_audio_buffer.speech_stopped"
    audio_end_ms: int
    item_id: str


ResponseItemStatus = Literal["in_progress", "completed", "incomplete"]


class ResponseItemInputTextContentPart(BaseModel):
    type: Literal["input_text"] = "input_text"
    text: str


class ResponseItemInputAudioContentPart(BaseModel):
    type: Literal["input_audio"] = "input_audio"
    transcript: Optional[str]


class ResponseItemTextContentPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ResponseItemAudioContentPart(BaseModel):
    type: Literal["audio"] = "audio"
    transcript: Optional[str]


ResponseItemContentPart = Annotated[
    Union[
        ResponseItemInputTextContentPart,
        ResponseItemInputAudioContentPart,
        ResponseItemTextContentPart,
        ResponseItemAudioContentPart,
    ],
    Field(discriminator="type"),
]


class ResponseItemBase(BaseModel):
    id: Optional[str]
    status: Optional[ResponseItemStatus] = None


class ResponseMessageItem(ResponseItemBase):
    type: MessageItemType = "message"
    role: MessageRole
    content: list[ResponseItemContentPart]


class ResponseFunctionCallItem(ResponseItemBase):
    type: Literal["function_call"] = "function_call"
    name: str
    call_id: str
    arguments: str


class ResponseFunctionCallOutputItem(ResponseItemBase):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: str
    output: str


ResponseItem = Annotated[
    Union[ResponseMessageItem, ResponseFunctionCallItem, ResponseFunctionCallOutputItem],
    Field(discriminator="type"),
]


class ItemCreatedMessage(ServerMessageBase):
    type: Literal["conversation.item.created"] = "conversation.item.created"
    previous_item_id: Optional[str]
    item: ResponseItem


class ItemTruncatedMessage(ServerMessageBase):
    type: Literal["conversation.item.truncated"] = "conversation.item.truncated"
    item_id: str
    content_index: int
    audio_end_ms: int


class ItemDeletedMessage(ServerMessageBase):
    type: Literal["conversation.item.deleted"] = "conversation.item.deleted"
    item_id: str


class ItemInputAudioTranscriptionCompletedMessage(ServerMessageBase):
    type: Literal["conversation.item.input_audio_transcription.completed"] = (
        "conversation.item.input_audio_transcription.completed"
    )
    item_id: str
    content_index: int
    transcript: str


class ItemInputAudioTranscriptionFailedMessage(ServerMessageBase):
    type: Literal["conversation.item.input_audio_transcription.failed"] = (
        "conversation.item.input_audio_transcription.failed"
    )
    item_id: str
    content_index: int
    error: RealtimeError


class ItemInputAudioTranscriptionDeltaMessage(ServerMessageBase):
    type: Literal["conversation.item.input_audio_transcription.delta"] = (
        "conversation.item.input_audio_transcription.delta"
    )
    item_id: str
    content_index: int
    delta: str


ResponseStatus = Literal["in_progress", "completed", "cancelled", "incomplete", "failed"]


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
    Union[ResponseCancelledDetails, ResponseIncompleteDetails, ResponseFailedDetails],
    Field(discriminator="type"),
]

class TokenDetails(BaseModel):
    text_tokens: int
    audio_tokens: int
    image_tokens: int

class InputTokenDetails(TokenDetails):
    cached_tokens: int
    cached_tokens_details: Optional[TokenDetails]

class Usage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int
    input_token_details: Optional[InputTokenDetails]
    output_token_details: Optional[TokenDetails]

class Response(BaseModel):
    id: str
    status: ResponseStatus
    status_details: Optional[ResponseStatusDetails]
    output: list[ResponseItem]
    usage: Optional[Usage]


class ResponseCreatedMessage(ServerMessageBase):
    type: Literal["response.created"] = "response.created"
    response: Response


class ResponseDoneMessage(ServerMessageBase):
    type: Literal["response.done"] = "response.done"
    response: Response


class ResponseOutputItemAddedMessage(ServerMessageBase):
    type: Literal["response.output_item.added"] = "response.output_item.added"
    response_id: str
    output_index: int
    item: ResponseItem


class ResponseOutputItemDoneMessage(ServerMessageBase):
    type: Literal["response.output_item.done"] = "response.output_item.done"
    response_id: str
    output_index: int
    item: ResponseItem


class ResponseContentPartAddedMessage(ServerMessageBase):
    type: Literal["response.content_part.added"] = "response.content_part.added"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    part: Annotated[
        ResponseItemContentPart, Field(alias="part", validation_alias=AliasChoices("part", "content"))
    ]  # TODO: this alias won't be needed when AOAI and OAI are in sync.


class ResponseContentPartDoneMessage(ServerMessageBase):
    type: Literal["response.content_part.done"] = "response.content_part.done"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    part: Annotated[
        ResponseItemContentPart, Field(alias="part", validation_alias=AliasChoices("part", "content"))
    ]  # TODO: this alias won't be needed when AOAI and OAI are in sync.


class ResponseTextDeltaMessage(ServerMessageBase):
    type: Literal["response.text.delta"] = "response.text.delta"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseTextDoneMessage(ServerMessageBase):
    type: Literal["response.text.done"] = "response.text.done"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    text: str


class ResponseAudioTranscriptDeltaMessage(ServerMessageBase):
    type: Literal["response.audio_transcript.delta"] = "response.audio_transcript.delta"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseAudioTranscriptDoneMessage(ServerMessageBase):
    type: Literal["response.audio_transcript.done"] = "response.audio_transcript.done"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    transcript: str


class ResponseAudioDeltaMessage(ServerMessageBase):
    type: Literal["response.audio.delta"] = "response.audio.delta"
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseAudioDoneMessage(ServerMessageBase):
    type: Literal["response.audio.done"] = "response.audio.done"
    response_id: str
    item_id: str
    output_index: int
    content_index: int


class ResponseFunctionCallArgumentsDeltaMessage(ServerMessageBase):
    type: Literal["response.function_call_arguments.delta"] = "response.function_call_arguments.delta"
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    delta: str


class ResponseFunctionCallArgumentsDoneMessage(ServerMessageBase):
    type: Literal["response.function_call_arguments.done"] = "response.function_call_arguments.done"
    response_id: str
    item_id: str
    output_index: int
    call_id: str
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
    Union[
        SessionUpdateMessage,
        InputAudioBufferAppendMessage,
        InputAudioBufferCommitMessage,
        InputAudioBufferClearMessage,
        ItemCreateMessage,
        ItemTruncateMessage,
        ItemDeleteMessage,
        ResponseCreateMessage,
        ResponseCancelMessage,
        UnknownClientMessage
    ],
    Field(discriminator="type"),
]

ServerMessageType = Annotated[
    Union[
        ErrorMessage,
        SessionCreatedMessage,
        SessionUpdatedMessage,
        InputAudioBufferCommittedMessage,
        InputAudioBufferClearedMessage,
        InputAudioBufferSpeechStartedMessage,
        InputAudioBufferSpeechStoppedMessage,
        ItemCreatedMessage,
        ItemTruncatedMessage,
        ItemDeletedMessage,
        ItemInputAudioTranscriptionCompletedMessage,
        ItemInputAudioTranscriptionFailedMessage,
        ItemInputAudioTranscriptionDeltaMessage,
        ResponseCreatedMessage,
        ResponseDoneMessage,
        ResponseOutputItemAddedMessage,
        ResponseOutputItemDoneMessage,
        ResponseContentPartAddedMessage,
        ResponseContentPartDoneMessage,
        ResponseTextDeltaMessage,
        ResponseTextDoneMessage,
        ResponseAudioTranscriptDeltaMessage,
        ResponseAudioTranscriptDoneMessage,
        ResponseAudioDeltaMessage,
        ResponseAudioDoneMessage,
        ResponseFunctionCallArgumentsDeltaMessage,
        ResponseFunctionCallArgumentsDoneMessage,
        RateLimitsUpdatedMessage,
        UnknownServerMessage
    ],
    Field(discriminator="type"),
]

# Dictionary mapping user message types to their respective classes.
USER_MESSAGE_CLASSES: dict[str, Type[UserMessageType]] = {
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
SERVER_MESSAGE_CLASSES: dict[str, Type[ServerMessageType]] = {
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

def create_user_message_from_dict(data: dict) -> UserMessageType:
    """
    Creates a user message object from a dictionary based on its 'type'.
    """
    event_type = data.get("type")

    if not event_type:
        return UnknownClientMessage(**data)
    # Use .get() to look up the class, providing a default if the key is not found.
    message_class = USER_MESSAGE_CLASSES.get(event_type, UnknownClientMessage)
    return message_class(**data)

def create_server_message_from_dict(data: dict) -> ServerMessageType:
    """
    Creates a server message object from a dictionary based on its 'type'.
    """
    event_type = data.get("type")

    if not event_type:
        return UnknownServerMessage(**data)

    message_class = SERVER_MESSAGE_CLASSES.get(event_type, UnknownServerMessage)
    return message_class(**data)

def create_message_from_dict(data: dict) -> ServerMessageType | UserMessageType:
    """
    Creates a message object from a dictionary based on its 'type'.
    """
    event_type = data.get("type") or ""
    if event_type in USER_MESSAGE_CLASSES.keys():
        cls =  USER_MESSAGE_CLASSES[event_type]
        return cls(**data)

    elif event_type in SERVER_MESSAGE_CLASSES.keys():
        cls =  USER_MESSAGE_CLASSES[event_type]
        return cls(**data)

    return UnknownClientMessage(**data)
