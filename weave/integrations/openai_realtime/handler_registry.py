from __future__ import annotations

from typing import Callable, Optional, Union, TypeVar, cast, overload, Literal
import logging
from weave.integrations.openai_realtime import models

logger = logging.getLogger(__name__)

Handler = Callable[[models.MessageType], None]

class EventHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    T_msg = TypeVar("T_msg", bound=models.MessageType)

    def register(self, event_type: str, handler: Callable[[T_msg], None]) -> None:
        # Safe cast: the registry only dispatches the matching event type
        self._handlers[event_type] = cast(Handler, handler)

    def get(self, event_type: str) -> Optional[Handler]:
        return self._handlers.get(event_type)

    def bulk_register(self, mapping: dict[str, Handler]) -> None:
        self._handlers.update(mapping)



SessionEventType = Union[Literal["session.created"], Literal["session.updated"], Literal["session.update"]]
InputAudioEventType = Union[
    Literal["input_audio_buffer.append"],
    Literal["input_audio_buffer.cleared"],
    Literal["input_audio_buffer.committed"],
    Literal["input_audio_buffer.speech_started"],
    Literal["input_audio_buffer.speech_stopped"],
]
ItemEventType = Union[
    Literal["conversation.item.create"],
    Literal["conversation.item.created"],
    Literal["conversation.item.truncated"],
    Literal["conversation.item.deleted"],
    Literal["conversation.item.input_audio_transcription.delta"],
    Literal["conversation.item.input_audio_transcription.completed"],
]
ResponseEventType = Union[
    Literal["response.create"],
    Literal["response.created"],
    Literal["response.cancel"],
    Literal["response.done"],
    Literal["response.output_item.added"],
    Literal["response.output_item.done"],
    Literal["response.content_part.added"],
    Literal["response.content_part.done"],
    Literal["response.text.delta"],
    Literal["response.text.done"],
    Literal["response.audio_transcript.delta"],
    Literal["response.audio_transcript.done"],
    Literal["response.audio.delta"],
    Literal["response.audio.done"],
    Literal["response.function_call_arguments.delta"],
    Literal["response.function_call_arguments.done"],
]
ErrorEventType = Literal["error"]
RateLimitsEventType = Literal["rate_limits.updated"]

SessionMessage = Union[models.SessionCreatedMessage, models.SessionUpdatedMessage, models.SessionUpdateMessage]
InputAudioBufferMessage = Union[
    models.InputAudioBufferAppendMessage,
    models.InputAudioBufferClearedMessage,
    models.InputAudioBufferCommittedMessage,
    models.InputAudioBufferSpeechStartedMessage,
    models.InputAudioBufferSpeechStoppedMessage,
]
ItemMessage = Union[
    models.ItemCreateMessage,
    models.ItemCreatedMessage,
    models.ItemTruncatedMessage,
    models.ItemDeletedMessage,
    models.ItemInputAudioTranscriptionDeltaMessage,
    models.ItemInputAudioTranscriptionCompletedMessage,
]
ResponseEvent = Union[
    models.ResponseCreateMessage,
    models.ResponseCreatedMessage,
    models.ResponseCancelMessage,
    models.ResponseDoneMessage,
    models.ResponseOutputItemAddedMessage,
    models.ResponseOutputItemDoneMessage,
    models.ResponseContentPartAddedMessage,
    models.ResponseContentPartDoneMessage,
    models.ResponseTextDeltaMessage,
    models.ResponseTextDoneMessage,
    models.ResponseAudioTranscriptDeltaMessage,
    models.ResponseAudioTranscriptDoneMessage,
    models.ResponseAudioDeltaMessage,
    models.ResponseAudioDoneMessage,
    models.ResponseFunctionCallArgumentsDeltaMessage,
    models.ResponseFunctionCallArgumentsDoneMessage,
]


class EventHandlerGroups:
    def __init__(self) -> None:
        self._dispatch: dict[str, Handler] = {}

    def _add(self, event_type: str, handler: Callable[..., None]) -> None:
        def wrapper(msg: models.MessageType, _h=handler) -> None:
            _h(msg)
        self._dispatch[event_type] = wrapper

    # Session
    @overload
    def register_session(self, event_type: Literal["session.created"], handler: Callable[[models.SessionCreatedMessage], None]) -> None: ...
    @overload
    def register_session(self, event_type: Literal["session.updated"], handler: Callable[[models.SessionUpdatedMessage], None]) -> None: ...
    @overload
    def register_session(self, event_type: Literal["session.update"], handler: Callable[[models.SessionUpdateMessage], None]) -> None: ...
    def register_session(self, event_type: SessionEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Input audio buffer
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.append"], handler: Callable[[models.InputAudioBufferAppendMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.cleared"], handler: Callable[[models.InputAudioBufferClearedMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.committed"], handler: Callable[[models.InputAudioBufferCommittedMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.speech_started"], handler: Callable[[models.InputAudioBufferSpeechStartedMessage], None]) -> None: ...
    @overload
    def register_input_audio(self, event_type: Literal["input_audio_buffer.speech_stopped"], handler: Callable[[models.InputAudioBufferSpeechStoppedMessage], None]) -> None: ...
    def register_input_audio(self, event_type: InputAudioEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Conversation items
    @overload
    def register_item(self, event_type: Literal["conversation.item.create"], handler: Callable[[models.ItemCreateMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.created"], handler: Callable[[models.ItemCreatedMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.truncated"], handler: Callable[[models.ItemTruncatedMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.deleted"], handler: Callable[[models.ItemDeletedMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.input_audio_transcription.delta"], handler: Callable[[models.ItemInputAudioTranscriptionDeltaMessage], None]) -> None: ...
    @overload
    def register_item(self, event_type: Literal["conversation.item.input_audio_transcription.completed"], handler: Callable[[models.ItemInputAudioTranscriptionCompletedMessage], None]) -> None: ...
    def register_item(self, event_type: ItemEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Responses
    @overload
    def register_response(self, event_type: Literal["response.create"], handler: Callable[[models.ResponseCreateMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.created"], handler: Callable[[models.ResponseCreatedMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.cancel"], handler: Callable[[models.ResponseCancelMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.done"], handler: Callable[[models.ResponseDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.output_item.added"], handler: Callable[[models.ResponseOutputItemAddedMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.output_item.done"], handler: Callable[[models.ResponseOutputItemDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.content_part.added"], handler: Callable[[models.ResponseContentPartAddedMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.content_part.done"], handler: Callable[[models.ResponseContentPartDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.text.delta"], handler: Callable[[models.ResponseTextDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.text.done"], handler: Callable[[models.ResponseTextDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio_transcript.delta"], handler: Callable[[models.ResponseAudioTranscriptDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio_transcript.done"], handler: Callable[[models.ResponseAudioTranscriptDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio.delta"], handler: Callable[[models.ResponseAudioDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.audio.done"], handler: Callable[[models.ResponseAudioDoneMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.function_call_arguments.delta"], handler: Callable[[models.ResponseFunctionCallArgumentsDeltaMessage], None]) -> None: ...
    @overload
    def register_response(self, event_type: Literal["response.function_call_arguments.done"], handler: Callable[[models.ResponseFunctionCallArgumentsDoneMessage], None]) -> None: ...
    def register_response(self, event_type: ResponseEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Error
    @overload
    def register_error(self, event_type: Literal["error"], handler: Callable[[models.ErrorMessage], None]) -> None: ...
    def register_error(self, event_type: ErrorEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    # Rate limits
    @overload
    def register_rate_limits(self, event_type: Literal["rate_limits.updated"], handler: Callable[[models.RateLimitsUpdatedMessage], None]) -> None: ...
    def register_rate_limits(self, event_type: RateLimitsEventType, handler: Callable[..., None]) -> None:
        self._add(event_type, handler)

    def to_dispatch_table(self) -> dict[str, Handler]:
        return dict(self._dispatch)


