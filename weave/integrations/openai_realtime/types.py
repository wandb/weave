"""OpenAI Realtime API Types"""

from typing import Any, Literal, Optional, Union

from typing_extensions import TypedDict

Base64EncodedAudioData = str


class ClientSecret(TypedDict):
    """Ephemeral key returned by the API."""

    value: str  # Ephemeral key usable in client environments
    expires_at: int  # Timestamp for when the token expires


class InputAudioTranscription(TypedDict):
    """Configuration for input audio transcription."""

    model: str  # The model to use for transcription


class Tool(TypedDict):
    """Tool (function) available to the model."""

    type: str  # The type of the tool, i.e. function
    name: str  # The name of the function
    description: str  # The description of the function
    parameters: dict[str, Any]  # Parameters of the function in JSON Schema


class TracingConfiguration(TypedDict):
    """Granular configuration for tracing."""

    workflow_name: str  # The name of the workflow to attach to this trace
    group_id: str  # The group id to attach to this trace
    metadata: dict[str, Any]  # The arbitrary metadata to attach to this trace


class TurnDetection(TypedDict):
    """Configuration for turn detection (Server VAD)."""

    type: str  # Type of turn detection, only server_vad is currently supported
    prefix_padding_ms: (
        int  # Amount of audio to include before VAD detected speech (defaults to 300)
    )
    silence_duration_ms: (
        int  # Duration of silence to detect speech stop (defaults to 500)
    )
    threshold: float  # Activation threshold for VAD (0.0 to 1.0, defaults to 0.5)


class RealtimeSession(TypedDict):
    """A Realtime session configuration object."""

    id: str  # Session ID
    object: Literal["realtime.session"]  # Object type identifier
    model: str  # The Realtime model used for this session
    modalities: list[
        Literal["audio", "text"]
    ]  # Set of modalities the model can respond with
    instructions: str  # Default system instructions prepended to model calls
    voice: Literal[
        "alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"
    ]  # Voice for model responses
    input_audio_format: Literal[
        "pcm16", "g711_ulaw", "g711_alaw"
    ]  # Format of input audio
    output_audio_format: Literal[
        "pcm16", "g711_ulaw", "g711_alaw"
    ]  # Format of output audio
    input_audio_transcription: Optional[
        InputAudioTranscription
    ]  # Configuration for input audio transcription
    turn_detection: Optional[
        TurnDetection
    ]  # Configuration for turn detection, null to turn off
    tools: list[Tool]  # Tools (functions) available to the model
    tool_choice: Union[
        Literal["auto", "none", "required"], str
    ]  # How the model chooses tools
    temperature: float  # Sampling temperature (0.6 to 1.2, defaults to 0.8)
    speed: float  # Speed of spoken response (0.25 to 1.5, defaults to 1.0)
    tracing: Union[
        Literal["auto"], TracingConfiguration, None
    ]  # Configuration for tracing, null to disable
    max_response_output_tokens: Union[
        int, Literal["inf"]
    ]  # Maximum output tokens (1-4096 or "inf")
    client_secret: ClientSecret  # Ephemeral key returned by the API


class RealtimeSessionUpdate(TypedDict):
    event_id: str
    session: RealtimeSession
    type: Literal["session.update"]


class InputAudioBufferAppend(TypedDict):
    event_id: Optional[str]
    type: Literal["input_audio_buffer.append"]
    audio: Base64EncodedAudioData
