---
title: Log Audio With Weave
---


:::tip[This is a notebook]

<a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/audio_with_weave.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>

<a href="https://github.com/wandb/weave/blob/master/docs/./notebooks/audio_with_weave.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/9/91/Octicons-mark-github.svg" alt="View in Github" height="15px" /><div>View in Github</div></div></a>

:::



<!--- @wandbcode{feedback-colab} -->


# How to use Weave with Audio Data: An OpenAI Example

This demo uses the OpenAI chat completions API with GPT 4o Audio Preview to generate audio responses to text prompts and track these in Weave.

<img src="https://i.imgur.com/OUfsZ2x.png"></img>

For the advanced use case, we leverage the OpenAI Realtime API to stream audio in realtime. Click the following thumbnail to view the video demonstration, or click [here](https://www.youtube.com/watch?v=lnnd73xDElw).

[![Everything Is AWESOME](https://img.youtube.com/vi/lnnd73xDElw/0.jpg)](https://www.youtube.com/watch?v=lnnd73xDElw "Everything Is AWESOME")


## Setup

Start by installing the OpenAI (`openai`) and Weave (`weave`) dependencies, as well as API key management dependencey `set-env`.



```python
%%capture
!pip install openai
!pip install weave
!pip install set-env-colab-kaggle-dotenv -q # for env var
```


```python
%%capture
# Temporary workaround to fix bug in openai:
# TypeError: Client.__init__() got an unexpected keyword argument 'proxies'
# See https://community.openai.com/t/error-with-openai-1-56-0-client-init-got-an-unexpected-keyword-argument-proxies/1040332/15
!pip install "httpx<0.28"
```

Next, load the required API keys for OpenAI and Weave. Here, we use set_env which is compatible with google colab's secret keys manager, and is an alternative to colab's specific `google.colab.userdata`. See: [here](https://pypi.org/project/set-env-colab-kaggle-dotenv/) for usage instructions.



```python
# Set environment variables.
from set_env import set_env

_ = set_env("OPENAI_API_KEY")
_ = set_env("WANDB_API_KEY")
```

And finally import the required libraries.



```python
import base64
import os
import time
import wave

import numpy as np
from IPython.display import display
from openai import OpenAI

import weave
```

## Audio Streaming and Storage Example


Now we will setup a call to OpenAI's completions endpoint with audio modality enabled. First create the OpenAI client and initiate a Weave project.



```python
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
weave.init("openai-audio-chat")
```

Now we will define our OpenAI completions request and add our Weave decorator (op).

Here, we define the function `prompt_endpont_and_log_trace`. This function has three primary steps:

1. We make a completion object using the `GPT 4o Audio Preview` model that supports text and audio inputs and outputs.

   - We prompt the model to count to 13 slowly with varying accents.
   - We set the completion to "stream".

2. We open a new output file to which the streamed data is writen chunk by chunk.

3. We return an open file handler to the audio file so Weave logs the audio data in the trace.



```python
SAMPLE_RATE = 22050


@weave.op()
def prompt_endpoint_and_log_trace(system_prompt=None, user_prompt=None):
    if not system_prompt:
        system_prompt = "You're the fastest counter in the world"
    if not user_prompt:
        user_prompt = "Count to 13 super super slow, enunciate each number with a dramatic flair, changing up accents as you go along. British, French, German, Spanish, etc."
    # Request from the OpenAI API with audio modality
    completion = client.chat.completions.create(
        model="gpt-4o-audio-preview",
        modalities=["text", "audio"],
        audio={"voice": "fable", "format": "pcm16"},
        stream=True,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    # Open a wave file for writing
    with wave.open("./output.wav", "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)  # Sample rate (adjust if needed)

        # Write chunks as they are streamed in from the API
        for chunk in completion:
            if (
                hasattr(chunk, "choices")
                and chunk.choices is not None
                and len(chunk.choices) > 0
            ):
                if (
                    hasattr(chunk.choices[0].delta, "audio")
                    and chunk.choices[0].delta.audio.get("data") is not None
                ):
                    # Decode the base64 audio data
                    audio_data = base64.b64decode(
                        chunk.choices[0].delta.audio.get("data")
                    )

                    # Write the current chunk to the wave file
                    wav_file.writeframes(audio_data)

    # Return the file to Weave op
    return wave.open("output.wav", "rb")
```

## Testing

Run the following cell. The system and user prompt will be stored in a Weave trace as well as the output audio.
After running the cell, click the link next to the "🍩" emoji to view your trace.



```python
from IPython.display import Audio, display

# Call the function to write the audio stream
prompt_endpoint_and_log_trace(
    system_prompt="You're the fastest counter in the world",
    user_prompt="Count to 13 super super slow, enunciate each number with a dramatic flair, changing up accents as you go along. British, French, German, Spanish, etc.",
)

# Display the updated audio stream
display(Audio("output.wav", rate=SAMPLE_RATE, autoplay=True))
```

# Advanced Usage: Realtime Audio API with Weave

<img src="https://i.imgur.com/ZiW3IVu.png"/>
<details>
<summary> (Advanced) Realtime Audio API with Weave </summary>
OpenAI's realtime API is a highly functional and reliable conversational API for building realtime audio and text assistants.

Please note:

- Review the cells in [Microphone Configuration](#microphone-configuration)
- Due to limitations of the Google Colab execution environment, **this must be run on your host machine** as a Jupyter Notebook. This cannot be ran in the browser.
  - On MacOS you will need to install `portaudio` via Brew (see [here](https://formulae.brew.sh/formula/portaudio)) for Pyaudio to function.
- OpenAI's Python SDK does not yet provide Realtime API support. We implement the complete OAI Realtime API schema in Pydantic for greater legibility, and may deprecate once official support is released.
- The `enable_audio_playback` toggle will cause playback of assistant outputted audio. Please note that **headphones are required if this is enabled**, as echo detection requires a highly complex implementation.


## Requirements Setup



```python
%%capture
!pip install numpy==2.0
!pip install weave
!pip install pyaudio # On mac, you may need to install portaudio first with `brew install portaudio`
!pip install websocket-client
!pip install set-env-colab-kaggle-dotenv -q # for env var
!pip install resampy
```


```python
import base64
import io
import json
import os
import threading
import time
import wave
from typing import Optional

import numpy as np
import pyaudio
import resampy
import websocket
from set_env import set_env

import weave
```


```python
# Set environment variables.
# See: https://pypi.org/project/set-env-colab-kaggle-dotenv/ for usage instructions.
_ = set_env("OPENAI_API_KEY")
_ = set_env("WANDB_API_KEY")
```

## Microphone Configuration

Run the following cell to find all available audio devices. Then, populate the `INPUT_DEVICE_INDEX` and the `OUTPUT_DEVICE_INDEX` based on the devices listed. Your input device will have at least 1 input channels, and your output device will have at least 1 output channels.



```python
# Get device list from pyaudio so we can configure the next cell
p = pyaudio.PyAudio()
devices_data = {i: p.get_device_info_by_index(i) for i in range(p.get_device_count())}
for i, device in devices_data.items():
    print(
        f"Found device @{i}: {device['name']} with sample rate: {device['defaultSampleRate']} and input channels: {device['maxInputChannels']} and output channels: {device['maxOutputChannels']}"
    )
```


```python
INPUT_DEVICE_INDEX = 3  # @param                                                 # Choose based on device list above. Make sure device has > 0 input channels.
OUTPUT_DEVICE_INDEX = 12  # @param                                                # Chose based on device list above. Make sure device has > 0 output channels.
enable_audio_playback = True  # @param {type:"boolean"}                           # Toggle on assistant audio playback. Requires headphones.

# Audio recording and streaming parameters
INPUT_DEVICE_CHANNELS = devices_data[INPUT_DEVICE_INDEX][
    "maxInputChannels"
]  # From device list above
SAMPLE_RATE = int(
    devices_data[INPUT_DEVICE_INDEX]["defaultSampleRate"]
)  # From device list above
CHUNK = int(SAMPLE_RATE / 10)  # Samples per frame
SAMPLE_WIDTH = p.get_sample_size(pyaudio.paInt16)  # Samples per frame for the format
CHUNK_DURATION = 0.3  # Seconds of audio per chunk sent to OAI API
OAI_SAMPLE_RATE = (
    24000  # OAI Sample Rate is 24kHz, we need this to play or save assistant audio
)
OUTPUT_DEVICE_CHANNELS = 1  # Set to 1 for mono output
```

## OpenAI Realtime API Schema Implementation

The OpenAI Python SDK does not yet provide Realtime API support. We implement the complete OAI Realtime API schema in Pydantic for greater legibility, and may deprecate once official support is released.

<details>
<summary> Pydantic Schema for OpenAI Realtime API (OpenAI's SDK lacks Realtime API support) </summary>



```python
from enum import Enum
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError


class BaseEvent(BaseModel):
    type: Union["ClientEventTypes", "ServerEventTypes"]
    event_id: Optional[str] = None  # Add event_id as an optional field for all events

    # def model_dump_json(self, *args, **kwargs):
    #     # Only include non-None fields
    #     return super().model_dump_json(*args, exclude_none=True, **kwargs)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: float


""" CLIENT EVENTS """


class ClientEventTypes(str, Enum):
    SESSION_UPDATE = "session.update"
    CONVERSATION_ITEM_CREATE = "conversation.item.create"
    CONVERSATION_ITEM_TRUNCATE = "conversation.item.truncate"
    CONVERSATION_ITEM_DELETE = "conversation.item.delete"
    RESPONSE_CREATE = "response.create"
    RESPONSE_CANCEL = "response.cancel"
    INPUT_AUDIO_BUFFER_APPEND = "input_audio_buffer.append"
    INPUT_AUDIO_BUFFER_COMMIT = "input_audio_buffer.commit"
    INPUT_AUDIO_BUFFER_CLEAR = "input_audio_buffer.clear"
    ERROR = "error"


#### Session Update
class TurnDetection(BaseModel):
    type: Literal["server_vad"]
    threshold: float = Field(..., ge=0.0, le=1.0)
    prefix_padding_ms: int
    silence_duration_ms: int


class InputAudioTranscription(BaseModel):
    model: Optional[str] = None


class ToolParameterProperty(BaseModel):
    type: str


class ToolParameter(BaseModel):
    type: str
    properties: dict[str, ToolParameterProperty]
    required: list[str]


class Tool(BaseModel):
    type: Literal["function", "code_interpreter", "file_search"]
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[ToolParameter] = None


class Session(BaseModel):
    modalities: Optional[list[str]] = None
    instructions: Optional[str] = None
    voice: Optional[str] = None
    input_audio_format: Optional[str] = None
    output_audio_format: Optional[str] = None
    input_audio_transcription: Optional[InputAudioTranscription] = None
    turn_detection: Optional[TurnDetection] = None
    tools: Optional[list[Tool]] = None
    tool_choice: Optional[str] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None


class SessionUpdate(BaseEvent):
    type: Literal[ClientEventTypes.SESSION_UPDATE] = ClientEventTypes.SESSION_UPDATE
    session: Session


#### Audio Buffers
class InputAudioBufferAppend(BaseEvent):
    type: Literal[ClientEventTypes.INPUT_AUDIO_BUFFER_APPEND] = (
        ClientEventTypes.INPUT_AUDIO_BUFFER_APPEND
    )
    audio: str


class InputAudioBufferCommit(BaseEvent):
    type: Literal[ClientEventTypes.INPUT_AUDIO_BUFFER_COMMIT] = (
        ClientEventTypes.INPUT_AUDIO_BUFFER_COMMIT
    )


class InputAudioBufferClear(BaseEvent):
    type: Literal[ClientEventTypes.INPUT_AUDIO_BUFFER_CLEAR] = (
        ClientEventTypes.INPUT_AUDIO_BUFFER_CLEAR
    )


#### Messages
class MessageContent(BaseModel):
    type: Literal["input_audio"]
    audio: str


class ConversationItemContent(BaseModel):
    type: Literal["input_text", "input_audio", "text", "audio"]
    text: Optional[str] = None
    audio: Optional[str] = None
    transcript: Optional[str] = None


class FunctionCallContent(BaseModel):
    call_id: str
    name: str
    arguments: str


class FunctionCallOutputContent(BaseModel):
    output: str


class ConversationItem(BaseModel):
    id: Optional[str] = None
    type: Literal["message", "function_call", "function_call_output"]
    status: Optional[Literal["completed", "in_progress", "incomplete"]] = None
    role: Literal["user", "assistant", "system"]
    content: list[
        Union[ConversationItemContent, FunctionCallContent, FunctionCallOutputContent]
    ]
    call_id: Optional[str] = None
    name: Optional[str] = None
    arguments: Optional[str] = None
    output: Optional[str] = None


class ConversationItemCreate(BaseEvent):
    type: Literal[ClientEventTypes.CONVERSATION_ITEM_CREATE] = (
        ClientEventTypes.CONVERSATION_ITEM_CREATE
    )
    item: ConversationItem


class ConversationItemTruncate(BaseEvent):
    type: Literal[ClientEventTypes.CONVERSATION_ITEM_TRUNCATE] = (
        ClientEventTypes.CONVERSATION_ITEM_TRUNCATE
    )
    item_id: str
    content_index: int
    audio_end_ms: int


class ConversationItemDelete(BaseEvent):
    type: Literal[ClientEventTypes.CONVERSATION_ITEM_DELETE] = (
        ClientEventTypes.CONVERSATION_ITEM_DELETE
    )
    item_id: str


#### Responses
class ResponseCreate(BaseEvent):
    type: Literal[ClientEventTypes.RESPONSE_CREATE] = ClientEventTypes.RESPONSE_CREATE


class ResponseCancel(BaseEvent):
    type: Literal[ClientEventTypes.RESPONSE_CANCEL] = ClientEventTypes.RESPONSE_CANCEL


# Update the Event union to include all event types
ClientEvent = Union[
    SessionUpdate,
    InputAudioBufferAppend,
    InputAudioBufferCommit,
    InputAudioBufferClear,
    ConversationItemCreate,
    ConversationItemTruncate,
    ConversationItemDelete,
    ResponseCreate,
    ResponseCancel,
]

""" SERVER EVENTS """


class ServerEventTypes(str, Enum):
    ERROR = "error"
    RESPONSE_AUDIO_TRANSCRIPT_DONE = "response.audio_transcript.done"
    RESPONSE_AUDIO_TRANSCRIPT_DELTA = "response.audio_transcript.delta"
    RESPONSE_AUDIO_DELTA = "response.audio.delta"
    SESSION_CREATED = "session.created"
    SESSION_UPDATED = "session.updated"
    CONVERSATION_CREATED = "conversation.created"
    INPUT_AUDIO_BUFFER_COMMITTED = "input_audio_buffer.committed"
    INPUT_AUDIO_BUFFER_CLEARED = "input_audio_buffer.cleared"
    INPUT_AUDIO_BUFFER_SPEECH_STARTED = "input_audio_buffer.speech_started"
    INPUT_AUDIO_BUFFER_SPEECH_STOPPED = "input_audio_buffer.speech_stopped"
    CONVERSATION_ITEM_CREATED = "conversation.item.created"
    CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED = (
        "conversation.item.input_audio_transcription.completed"
    )
    CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED = (
        "conversation.item.input_audio_transcription.failed"
    )
    CONVERSATION_ITEM_TRUNCATED = "conversation.item.truncated"
    CONVERSATION_ITEM_DELETED = "conversation.item.deleted"
    RESPONSE_CREATED = "response.created"
    RESPONSE_DONE = "response.done"
    RESPONSE_OUTPUT_ITEM_ADDED = "response.output_item.added"
    RESPONSE_OUTPUT_ITEM_DONE = "response.output_item.done"
    RESPONSE_CONTENT_PART_ADDED = "response.content_part.added"
    RESPONSE_CONTENT_PART_DONE = "response.content_part.done"
    RESPONSE_TEXT_DELTA = "response.text.delta"
    RESPONSE_TEXT_DONE = "response.text.done"
    RESPONSE_AUDIO_DONE = "response.audio.done"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA = "response.function_call_arguments.delta"
    RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE = "response.function_call_arguments.done"
    RATE_LIMITS_UPDATED = "rate_limits.updated"


#### Errors
class ErrorDetails(BaseModel):
    type: Optional[str] = None
    code: Optional[str] = None
    message: Optional[str] = None
    param: Optional[str] = None


class ErrorEvent(BaseEvent):
    type: Literal[ServerEventTypes.ERROR] = ServerEventTypes.ERROR
    error: ErrorDetails


#### Session
class SessionCreated(BaseEvent):
    type: Literal[ServerEventTypes.SESSION_CREATED] = ServerEventTypes.SESSION_CREATED
    session: Session


class SessionUpdated(BaseEvent):
    type: Literal[ServerEventTypes.SESSION_UPDATED] = ServerEventTypes.SESSION_UPDATED
    session: Session


#### Conversation
class Conversation(BaseModel):
    id: str
    object: Literal["realtime.conversation"]


class ConversationCreated(BaseEvent):
    type: Literal[ServerEventTypes.CONVERSATION_CREATED] = (
        ServerEventTypes.CONVERSATION_CREATED
    )
    conversation: Conversation


class ConversationItemCreated(BaseEvent):
    type: Literal[ServerEventTypes.CONVERSATION_ITEM_CREATED] = (
        ServerEventTypes.CONVERSATION_ITEM_CREATED
    )
    previous_item_id: Optional[str] = None
    item: ConversationItem


class ConversationItemInputAudioTranscriptionCompleted(BaseEvent):
    type: Literal[
        ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED
    ] = ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED
    item_id: str
    content_index: int
    transcript: str


class ConversationItemInputAudioTranscriptionFailed(BaseEvent):
    type: Literal[
        ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED
    ] = ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED
    item_id: str
    content_index: int
    error: dict[str, Any]


class ConversationItemTruncated(BaseEvent):
    type: Literal[ServerEventTypes.CONVERSATION_ITEM_TRUNCATED] = (
        ServerEventTypes.CONVERSATION_ITEM_TRUNCATED
    )
    item_id: str
    content_index: int
    audio_end_ms: int


class ConversationItemDeleted(BaseEvent):
    type: Literal[ServerEventTypes.CONVERSATION_ITEM_DELETED] = (
        ServerEventTypes.CONVERSATION_ITEM_DELETED
    )
    item_id: str


#### Response
class ResponseUsage(BaseModel):
    total_tokens: int
    input_tokens: int
    output_tokens: int
    input_token_details: Optional[dict[str, int]] = None
    output_token_details: Optional[dict[str, int]] = None


class ResponseOutput(BaseModel):
    id: str
    object: Literal["realtime.item"]
    type: str
    status: str
    role: str
    content: list[dict[str, Any]]


class ResponseContentPart(BaseModel):
    type: str
    text: Optional[str] = None


class ResponseOutputItemContent(BaseModel):
    type: str
    text: Optional[str] = None


class ResponseStatusDetails(BaseModel):
    type: str
    reason: str


class ResponseOutputItem(BaseModel):
    id: str
    object: Literal["realtime.item"]
    type: str
    status: str
    role: str
    content: list[ResponseOutputItemContent]


class Response(BaseModel):
    id: str
    object: Literal["realtime.response"]
    status: str
    status_details: Optional[ResponseStatusDetails] = None
    output: list[ResponseOutput]
    usage: Optional[ResponseUsage]


class ResponseCreated(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_CREATED] = ServerEventTypes.RESPONSE_CREATED
    response: Response


class ResponseDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_DONE] = ServerEventTypes.RESPONSE_DONE
    response: Response


class ResponseOutputItemAdded(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_OUTPUT_ITEM_ADDED] = (
        ServerEventTypes.RESPONSE_OUTPUT_ITEM_ADDED
    )
    response_id: str
    output_index: int
    item: ResponseOutputItem


class ResponseOutputItemDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_OUTPUT_ITEM_DONE] = (
        ServerEventTypes.RESPONSE_OUTPUT_ITEM_DONE
    )
    response_id: str
    output_index: int
    item: ResponseOutputItem


class ResponseContentPartAdded(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_CONTENT_PART_ADDED] = (
        ServerEventTypes.RESPONSE_CONTENT_PART_ADDED
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    part: ResponseContentPart


class ResponseContentPartDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_CONTENT_PART_DONE] = (
        ServerEventTypes.RESPONSE_CONTENT_PART_DONE
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    part: ResponseContentPart


#### Response Text
class ResponseTextDelta(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_TEXT_DELTA] = (
        ServerEventTypes.RESPONSE_TEXT_DELTA
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    delta: str


class ResponseTextDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_TEXT_DONE] = (
        ServerEventTypes.RESPONSE_TEXT_DONE
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int
    text: str


#### Response Audio
class ResponseAudioTranscriptDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DONE] = (
        ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DONE
    )
    transcript: str


class ResponseAudioTranscriptDelta(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DELTA] = (
        ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DELTA
    )
    delta: str


class ResponseAudioDelta(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_AUDIO_DELTA] = (
        ServerEventTypes.RESPONSE_AUDIO_DELTA
    )
    response_id: str
    item_id: str
    delta: str


class ResponseAudioDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_AUDIO_DONE] = (
        ServerEventTypes.RESPONSE_AUDIO_DONE
    )
    response_id: str
    item_id: str
    output_index: int
    content_index: int


class InputAudioBufferCommitted(BaseEvent):
    type: Literal[ServerEventTypes.INPUT_AUDIO_BUFFER_COMMITTED] = (
        ServerEventTypes.INPUT_AUDIO_BUFFER_COMMITTED
    )
    previous_item_id: Optional[str] = None
    item_id: Optional[str] = None
    event_id: Optional[str] = None


class InputAudioBufferCleared(BaseEvent):
    type: Literal[ServerEventTypes.INPUT_AUDIO_BUFFER_CLEARED] = (
        ServerEventTypes.INPUT_AUDIO_BUFFER_CLEARED
    )


class InputAudioBufferSpeechStarted(BaseEvent):
    type: Literal[ServerEventTypes.INPUT_AUDIO_BUFFER_SPEECH_STARTED] = (
        ServerEventTypes.INPUT_AUDIO_BUFFER_SPEECH_STARTED
    )
    audio_start_ms: int
    item_id: str


class InputAudioBufferSpeechStopped(BaseEvent):
    type: Literal[ServerEventTypes.INPUT_AUDIO_BUFFER_SPEECH_STOPPED] = (
        ServerEventTypes.INPUT_AUDIO_BUFFER_SPEECH_STOPPED
    )
    audio_end_ms: int
    item_id: str


#### Function Calls
class ResponseFunctionCallArgumentsDelta(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA] = (
        ServerEventTypes.RESPONSE_FUNCTION_CALL_ARGUMENTS_DELTA
    )
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    delta: str


class ResponseFunctionCallArgumentsDone(BaseEvent):
    type: Literal[ServerEventTypes.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE] = (
        ServerEventTypes.RESPONSE_FUNCTION_CALL_ARGUMENTS_DONE
    )
    response_id: str
    item_id: str
    output_index: int
    call_id: str
    arguments: str


#### Rate Limits
class RateLimit(BaseModel):
    name: str
    limit: int
    remaining: int
    reset_seconds: float


class RateLimitsUpdated(BaseEvent):
    type: Literal[ServerEventTypes.RATE_LIMITS_UPDATED] = (
        ServerEventTypes.RATE_LIMITS_UPDATED
    )
    rate_limits: list[RateLimit]


ServerEvent = Union[
    ErrorEvent,
    ConversationCreated,
    ResponseAudioTranscriptDone,
    ResponseAudioTranscriptDelta,
    ResponseAudioDelta,
    ResponseCreated,
    ResponseDone,
    ResponseOutputItemAdded,
    ResponseOutputItemDone,
    ResponseContentPartAdded,
    ResponseContentPartDone,
    ResponseTextDelta,
    ResponseTextDone,
    ResponseAudioDone,
    ConversationItemInputAudioTranscriptionCompleted,
    SessionCreated,
    SessionUpdated,
    InputAudioBufferCleared,
    InputAudioBufferSpeechStarted,
    InputAudioBufferSpeechStopped,
    ConversationItemCreated,
    ConversationItemInputAudioTranscriptionFailed,
    ConversationItemTruncated,
    ConversationItemDeleted,
    RateLimitsUpdated,
]

EVENT_TYPE_TO_MODEL = {
    ServerEventTypes.ERROR: ErrorEvent,
    ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DONE: ResponseAudioTranscriptDone,
    ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DELTA: ResponseAudioTranscriptDelta,
    ServerEventTypes.RESPONSE_AUDIO_DELTA: ResponseAudioDelta,
    ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED: ConversationItemInputAudioTranscriptionCompleted,
    ServerEventTypes.SESSION_CREATED: SessionCreated,
    ServerEventTypes.SESSION_UPDATED: SessionUpdated,
    ServerEventTypes.CONVERSATION_CREATED: ConversationCreated,
    ServerEventTypes.INPUT_AUDIO_BUFFER_COMMITTED: InputAudioBufferCommitted,
    ServerEventTypes.INPUT_AUDIO_BUFFER_CLEARED: InputAudioBufferCleared,
    ServerEventTypes.INPUT_AUDIO_BUFFER_SPEECH_STARTED: InputAudioBufferSpeechStarted,
    ServerEventTypes.INPUT_AUDIO_BUFFER_SPEECH_STOPPED: InputAudioBufferSpeechStopped,
    ServerEventTypes.CONVERSATION_ITEM_CREATED: ConversationItemCreated,
    ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_FAILED: ConversationItemInputAudioTranscriptionFailed,
    ServerEventTypes.CONVERSATION_ITEM_TRUNCATED: ConversationItemTruncated,
    ServerEventTypes.CONVERSATION_ITEM_DELETED: ConversationItemDeleted,
    ServerEventTypes.RESPONSE_CREATED: ResponseCreated,
    ServerEventTypes.RESPONSE_DONE: ResponseDone,
    ServerEventTypes.RESPONSE_OUTPUT_ITEM_ADDED: ResponseOutputItemAdded,
    ServerEventTypes.RESPONSE_OUTPUT_ITEM_DONE: ResponseOutputItemDone,
    ServerEventTypes.RESPONSE_CONTENT_PART_ADDED: ResponseContentPartAdded,
    ServerEventTypes.RESPONSE_CONTENT_PART_DONE: ResponseContentPartDone,
    ServerEventTypes.RESPONSE_TEXT_DELTA: ResponseTextDelta,
    ServerEventTypes.RESPONSE_TEXT_DONE: ResponseTextDone,
    ServerEventTypes.RESPONSE_AUDIO_DONE: ResponseAudioDone,
    ServerEventTypes.RATE_LIMITS_UPDATED: RateLimitsUpdated,
}


def parse_server_event(event_data: dict) -> ServerEvent:
    event_type = event_data.get("type")
    if not event_type:
        raise ValueError("Event data is missing 'type' field")

    model_class = EVENT_TYPE_TO_MODEL.get(event_type)
    if not model_class:
        raise ValueError(f"Unknown event type: {event_type}")

    try:
        return model_class(**event_data)
    except ValidationError as e:
        raise ValueError(f"Failed to parse event of type {event_type}: {str(e)}")
```

</details>


## Audio Stream Writer (To Disk and In Memory)



```python
class StreamingWavWriter:
    """Writes audio integer or byte array chunks to a WAV file."""

    wav_file = None
    buffer = None
    in_memory = False

    def __init__(
        self,
        filename=None,
        channels=INPUT_DEVICE_CHANNELS,
        sample_width=SAMPLE_WIDTH,
        framerate=SAMPLE_RATE,
    ):
        self.in_memory = filename is None
        if self.in_memory:
            self.buffer = io.BytesIO()
            self.wav_file = wave.open(self.buffer, "wb")
        else:
            self.wav_file = wave.open(filename, "wb")

        self.wav_file.setnchannels(channels)
        self.wav_file.setsampwidth(sample_width)
        self.wav_file.setframerate(framerate)

    def append_int16_chunk(self, int16_data):
        if int16_data is not None:
            self.wav_file.writeframes(
                int16_data.tobytes()
                if isinstance(int16_data, np.ndarray)
                else int16_data
            )

    def close(self):
        self.wav_file.close()

    def get_wav_buffer(self):
        assert self.in_memory, "Buffer only available if stream is in memory."
        return self.buffer
```

## Realtime Audio Model

The realtime (RT) audio model uses a websocket to send events to OpenAI's Realtime audio API. This works as follows:

1.  **init:** We initialize local buffers (input audio) and streams (assistant playback stream, user audio disk writer stream) and open a connection to the Realtime API.
2.  **receive_messages_thread**: A thread handles receiving messages from the API. Four primary event types are handled: - RESPONSE_AUDIO_TRANSCRIPT_DONE:

            The server indicates the assistant's response is completed and provides the transcript.

        - CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED:

            The server indicates the user's audio has been transcribed, and sends the transcript of the user's audio. We log the transcript to Weave and print it for the user.

        - RESPONSE_AUDIO_DELTA:

            The server sends a new chunk of assistant response audio. We append this to the ongoing response data via the response ID, and add this to the output stream for playback.

        - RESPONSE_DONE:

            The server indicates completion of an assistant response. We get all audio chunks associated with the response, as well as the transcript, and log these in Weave.

    3.**send_audio**: A handler appends user audio chunks to a buffer, and sends chunks of audio when the audio buffer reaches a certain size.



```python
class RTAudioModel(weave.Model):
    """Model class for realtime e2e audio OpenAI model interaction with Whisper user transcription for logging."""

    realtime_model_name: str = "gpt-4o-realtime-preview-2024-10-01"  # realtime e2e audio only model interaction

    stop_event: Optional[threading.Event] = threading.Event()  # Event to stop the model
    ws: Optional[websocket.WebSocket] = None  # Websocket for OpenAI communications

    user_wav_writer: Optional[StreamingWavWriter] = (
        None  # Stream for writing user output to file
    )
    input_audio_buffer: Optional[np.ndarray] = None  # Buffer for user audio chunks
    assistant_outputs: dict[str, StreamingWavWriter] = (
        None  # Assistant outputs aggregated to send to weave
    )
    playback_stream: Optional[pyaudio.Stream] = (
        None  # Playback stream for playing assistant responses
    )

    def __init__(self):
        super().__init__()
        self.stop_event.clear()
        self.user_wav_writer = StreamingWavWriter(
            filename="user_audio.wav", framerate=SAMPLE_RATE
        )
        self.input_audio_buffer = np.array([], dtype=np.int16)
        self.ws = websocket.WebSocket()
        self.assistant_outputs = {}

        # Open the assistant audio playback stream if enabled
        if enable_audio_playback:
            self.playback_stream = pyaudio.PyAudio().open(
                format=pyaudio.paInt16,
                channels=OUTPUT_DEVICE_CHANNELS,
                rate=OAI_SAMPLE_RATE,
                output=True,
                output_device_index=OUTPUT_DEVICE_INDEX,
            )

        # Connect Websocket
        try:
            self.ws.connect(
                f"wss://api.openai.com/v1/realtime?model={self.realtime_model_name}",
                header={
                    "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY')}",
                    "OpenAI-Beta": "realtime=v1",
                },
            )

            # Send config msg
            config_event = SessionUpdate(
                session=Session(
                    modalities=["text", "audio"],  # modalities to use
                    input_audio_transcription=InputAudioTranscription(
                        model="whisper-1"
                    ),  # whisper-1 for transcription
                    turn_detection=TurnDetection(
                        type="server_vad",
                        threshold=0.3,
                        prefix_padding_ms=300,
                        silence_duration_ms=600,
                    ),  # server VAD to detect silence
                )
            )
            self.ws.send(config_event.model_dump_json(exclude_none=True))
            self.log_ws_message(config_event.model_dump_json(exclude_none=True), "Sent")

            # Start listener
            websocket_thread = threading.Thread(target=self.receive_messages_thread)
            websocket_thread.daemon = True
            websocket_thread.start()

        except Exception as e:
            print(f"Error connecting to WebSocket: {e}")

    ##### Weave Integration and Message Handlers #####
    def handle_assistant_response_audio_delta(self, data: ResponseAudioDelta):
        if data.response_id not in self.assistant_outputs:
            self.assistant_outputs[data.response_id] = StreamingWavWriter(
                framerate=OAI_SAMPLE_RATE
            )

        data_bytes = base64.b64decode(data.delta)
        self.assistant_outputs[data.response_id].append_int16_chunk(data_bytes)

        if enable_audio_playback:
            self.playback_stream.write(data_bytes)

        return {"assistant_audio": data_bytes}

    @weave.op()
    def handle_assistant_response_done(self, data: ResponseDone):
        wave_file_stream = self.assistant_outputs[data.response.id]
        wave_file_stream.close()
        wave_file_stream.buffer.seek(0)
        weave_payload = {
            "assistant_audio": wave.open(wave_file_stream.get_wav_buffer(), "rb"),
            "assistant_transcript": data.response.output[0]
            .content[0]
            .get("transcript", "Transcript Unavailable."),
        }
        return weave_payload

    @weave.op()
    def handle_user_transcription_done(
        self, data: ConversationItemInputAudioTranscriptionCompleted
    ):
        return {"user_transcript": data.transcript}

    ##### Message Receiver and Sender #####
    def receive_messages_thread(self):
        while not self.stop_event.is_set():
            try:
                data = json.loads(self.ws.recv())
                self.log_ws_message(json.dumps(data, indent=2))

                parsed_event = parse_server_event(data)

                if parsed_event.type == ServerEventTypes.RESPONSE_AUDIO_TRANSCRIPT_DONE:
                    print("Assistant: ", parsed_event.transcript)
                elif (
                    parsed_event.type
                    == ServerEventTypes.CONVERSATION_ITEM_INPUT_AUDIO_TRANSCRIPTION_COMPLETED
                ):
                    print("User: ", parsed_event.transcript)
                    self.handle_user_transcription_done(parsed_event)
                elif parsed_event.type == ServerEventTypes.RESPONSE_AUDIO_DELTA:
                    self.handle_assistant_response_audio_delta(parsed_event)
                elif parsed_event.type == ServerEventTypes.RESPONSE_DONE:
                    self.handle_assistant_response_done(parsed_event)
                elif parsed_event.type == ServerEventTypes.ERROR:
                    print(
                        f"\nError from server: {parsed_event.error.model_dump_json(exclude_none=True)}"
                    )
            except websocket.WebSocketConnectionClosedException:
                print("\nWebSocket connection closed")
                break
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"\nError in receive_messages: {e}")
                break

    def send_audio(self, audio_chunk):
        if self.ws and self.ws.connected:
            self.input_audio_buffer = np.append(
                self.input_audio_buffer, np.frombuffer(audio_chunk, dtype=np.int16)
            )
            if len(self.input_audio_buffer) >= SAMPLE_RATE * CHUNK_DURATION:
                try:
                    # Resample audio to OAI sample rate
                    resampled_audio = (
                        resampy.resample(
                            self.input_audio_buffer, SAMPLE_RATE, OAI_SAMPLE_RATE
                        )
                        if SAMPLE_RATE != OAI_SAMPLE_RATE
                        else self.input_audio_buffer
                    )

                    # Send audio chunk to OAI API
                    audio_event = InputAudioBufferAppend(
                        audio=base64.b64encode(
                            resampled_audio.astype(np.int16).tobytes()
                        ).decode("utf-8")  # Convert audio array to b64 bytes
                    )
                    self.ws.send(audio_event.model_dump_json(exclude_none=True))
                    self.log_ws_message(
                        audio_event.model_dump_json(exclude_none=True), "Sent"
                    )
                finally:
                    self.user_wav_writer.append_int16_chunk(self.input_audio_buffer)

                    # Clear the audio buffer
                    self.input_audio_buffer = np.array([], dtype=np.int16)
        else:
            print("Error sending audio: websocket not initialized.")

    ##### General Utility Functions #####
    def log_ws_message(self, message, direction="Received"):
        with open("websocket_log.txt", "a") as log_file:
            log_file.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {direction}: {message}\n"
            )

    def stop(self):
        self.stop_event.set()

        if self.ws:
            self.ws.close()

        self.user_wav_writer.close()
```

## Audio recorder

We use a pyaudio input stream with a handler linked to the `send_audio` method of the RTAudio model. The stream is returned to the main thread so it can be safely exited upon program completion.



```python
# Audio capture stream
def record_audio(realtime_model: RTAudioModel) -> pyaudio.Stream:
    """Setup a Pyaudio input stream and use the RTAudioModel as a callback for streaming data."""

    def audio_callback(in_data, frame_count, time_info, status):
        realtime_model.send_audio(in_data)
        return (None, pyaudio.paContinue)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=INPUT_DEVICE_CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        input_device_index=INPUT_DEVICE_INDEX,
        frames_per_buffer=CHUNK,
        stream_callback=audio_callback,
    )
    stream.start_stream()

    print("Recording started. Please begin speaking to your personal assistant...")
    return stream
```

## Main Thread (Run me!)

The main thread initiates a Realtime Audio Model with Weave integrated. Next, a reccording is opened and we wait for a keyboard interrupt from the user.



```python
weave.init(project_name="realtime-oai-audio-testing")

realtime_model = RTAudioModel()

if realtime_model.ws and realtime_model.ws.connected:
    recording_stream: pyaudio.Stream = record_audio(realtime_model)

    try:
        while not realtime_model.stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error in main loop: {e}")
        import traceback

        traceback.print_exc()
    finally:
        print("Exiting...")
        realtime_model.stop()
        if recording_stream and recording_stream.is_active():
            recording_stream.stop_stream()
            recording_stream.close()
else:
    print(
        "WebSocket connection failed. Please check your API key and internet connection."
    )
```

</details>

