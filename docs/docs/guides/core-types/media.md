# Logging media

Weave supports logging and displaying multiple first class media types. Log images with `PIL.Image.Image` and audio with `wave.Wave_read` either directly with the object API, or as the inputs or output of an op.

## Images

Logging type: `PIL.Image.Image`. Here is an example of logging an image with the OpenAI DALL-E API:

```python
import weave
from openai import OpenAI
import requests
from PIL import Image


weave.init('image-example')
client = OpenAI()

@weave.op
def generate_image(prompt: str) -> Image:
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url
    image_response = requests.get(image_url, stream=True)
    image = Image.open(image_response.raw)

    # return a PIL.Image.Image object to be logged as an image
    return image

generate_image("a cat with a pumpkin hat")
```

This image will be logged to weave and automatically displayed in the UI. The following is the trace view for above.

![Screenshot of pumpkin cat trace view](imgs/cat-pumpkin-trace.png)

## Audio

Logging type: `wave.Wave_read`. Here is an example of logging an audio file using openai's speech generation API.

```python
import weave
from openai import OpenAI
import wave


weave.init("audio-example")
client = OpenAI()


@weave.op
def make_audio_file_streaming(text: str) -> wave.Wave_read:
    with client.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="alloy",
        input=text,
        response_format="wav",
    ) as res:
        res.stream_to_file("output.wav")

    # return a wave.Wave_read object to be logged as audio
    return wave.open("output.wav")

make_audio_file_streaming("Hello, how are you?")
```

This audio will be logged to weave and automatically displayed in the UI, with an audio player. The player can be expanded to view the raw audio waveform, in addition to a download button.

![Screenshot of audio trace view](imgs/audio-trace.png)
