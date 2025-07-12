import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Logging media

Weave supports logging and displaying video, images, audio, PDFs, and CSVs.

## Video

Weave automatically logs videos using [`moviepy`](https://zulko.github.io/moviepy/). This allows you to pass video inputs and outputs to traced functions, and Weave will automatically handle uploading and storing video data.

:::note
Video support is currently only available in Python.
:::

For usage information, see [Video Support](../tracking/video).

## Images

Logging type: `PIL.Image.Image`. 

:::important
Base64-encoded image strings (e.g., `data:image/jpeg;base64,...`) are technically supported but discouraged. They can cause performance issues and should only be used if absolutely necessary (e.g., for integration with specific APIs).
:::

The following example shows how to log an image generated via the OpenAI DALL-E API:

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
  
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```typescript
    import {OpenAI} from 'openai';
    import * as weave from 'weave';

    async function main() {
        const client = await weave.init('image-example');
        const openai = new OpenAI();

        const generateImage = weave.op(async (prompt: string) => {
            const response = await openai.images.generate({
                model: 'dall-e-3',
                prompt: prompt,
                size: '1024x1024',
                quality: 'standard',
                n: 1,
            });
            const imageUrl = response.data[0].url;
            const imgResponse = await fetch(imageUrl);
            const data = Buffer.from(await imgResponse.arrayBuffer());

            return weave.weaveImage({data});
        });

        generateImage('a cat with a pumpkin hat');
    }

    main();
    ```

  </TabItem>
</Tabs>

This image is logged to Weave and automatically displayed in the UI. 

![Screenshot of pumpkin cat trace view](imgs/cat-pumpkin-trace.png)

### Resize large images before logging

It can be helpful to resize images before logging to reduce UI rendering cost and storage impact. You can use `postprocess_output` in your `@weave.op` to resize an image.

```python
from dataclasses import dataclass
from typing import Any
from PIL import Image
import weave

weave.init('image-resize-example')

# Custom output type
@dataclass
class ImageResult:
    label: str
    image: Image.Image

# Resize helper
def resize_image(image: Image.Image, max_size=(512, 512)) -> Image.Image:
    image = image.copy()
    image.thumbnail(max_size, Image.ANTIALIAS)
    return image

# Postprocess output to resize image before logging
def postprocess_output(output: ImageResult) -> ImageResult:
    resized = resize_image(output.image)
    return ImageResult(label=output.label, image=resized)

@weave.op(postprocess_output=postprocess_output)
def generate_large_image() -> ImageResult:
    # Create an example image to process (e.g., 2000x2000 red square)
    img = Image.new("RGB", (2000, 2000), color="red")
    return ImageResult(label="big red square", image=img)

generate_large_image()
```

## Audio

Logging type: `wave.Wave_read`. 

The following example shows how to log an audio file using OpenAI's speech generation API.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
  
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```typescript
    import {OpenAI} from 'openai';
    import * as weave from 'weave';

    async function main() {
        await weave.init('audio-example');
        const openai = new OpenAI();

        const makeAudioFileStreaming = weave.op(async function audio(text: string) {
            const response = await openai.audio.speech.create({
                model: 'tts-1',
                voice: 'alloy',
                input: text,
                response_format: 'wav',
            });

            const chunks: Uint8Array[] = [];
            for await (const chunk of response.body) {
                chunks.push(chunk);
            }
            return weave.weaveAudio({data: Buffer.concat(chunks)});
        });

        await makeAudioFileStreaming('Hello, how are you?');
    }

    main();
    ```

  </TabItem>
</Tabs>

This audio is logged to Weave and automatically displayed in the UI, along with an audio player. In the audio player, you can view and download the raw audio waveform.

![Screenshot of audio trace view](imgs/audio-trace.png)

:::tip
Try our cookbook for [Audio Logging](/reference/gen_notebooks/audio_with_weave) or <a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/audio_with_weave.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>. The cookbook also includes an advanced example of a Real Time Audio API based assistant integrated with Weave.
:::

## `Content` for binary content handling

:::note
`Content` replaces the deprecated `weave.File` class and is intended as its more general and flexible successor.
:::

The `Content` class wraps binary data with rich metadata. It supports a wide range of input types and is designed to be flexible and extensible. You can use it directly, or with `Annotated[...]` to allow Weave to infer or enforce content types in your ops. The `Content` class provides the following key benefits:

- Unified interface for files, bytes, and base64
- Optional `type_hint` support to help with MIME inference
- Automatic metadata extraction (filename, extension, size, etc.)
- Works with Weave's UI for displaying binary objects (e.g., MP3s, PDFs, images)

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>

    ### Constructor definition for `Content[T]`

    The constructor for `Content` is as follows:

    ```python
    Content(input: Any, type_hint: str | None = None, /, **kwargs)
    ```

    #### Parameters:

    - `input` (`Path | str | bytes | object`): The data source
    - `type_hint` (`str | None`): Optional MIME type or file extension (e.g., `"image/png"` or `"pdf"`)
    - `**kwargs`: Optional metadata (For details, see [Properties](#properties))
        - `filename`
        - `mimetype`
        - `extension`
        - `original_path`
        - `extra` (`dict` for any additional metadata)

    #### Input formats

    `Content` accepts the following input formats:

    - File paths (as a string or `Path`): Read from disk
    - Base64 strings: Automatically decoded
    - Bytes: Used directly
    - Custom objects (experimental): Must support `to_bytes` or custom handlers

    ### Properties

    | Property        | Type             | Description                             |
    | --------------- | ---------------- | --------------------------------------- |
    | `data`          | `bytes`          | Raw binary content                      |
    | `metadata`      | `dict[str, Any]` | All metadata except `data`              |
    | `size`          | `int`            | Size of content in bytes                |
    | `filename`      | `str`            | Extracted or provided filename          |
    | `extension`     | `str`            | File extension (e.g., `"jpg"`, `"mp3"`) |
    | `mimetype`      | `str`            | MIME type (e.g., `"image/jpeg"`)        |
    | `original_path` | `str \| None`     | Source file path, if applicable         |

    ### Methods

    - `save(dest: str | Path) -> None`: Save content to a file
    - `open() -> bool`: Open file using system default (currently supports files with a path only)

    ### Helper functions

    These low-level helpers create content handlers explicitly:

    - `create_bytes_content(data: bytes, **kwargs)`
    - `create_file_content(path: str | Path, **kwargs)`
    - `create_b64_content(data: str | bytes, **kwargs)`

    ### Usage examples

    #### Create `Content` from a path

    In the following example, `Content` is created from a `.jpg`. The filename and path are parsed as `file.jpg`, and the mimetype is parsed from the filename.

    ```python
    content = Content("assets/photo.jpg")
    print(content.mimetype, content.size)
    ```

    #### Create `Content` from Base64

    ```python
    content = Content(base64_string)
    print(content.metadata)
    ```

    #### Create `Content` from bytes and metadata

    ```python
    content = Content(data_bytes, filename="audio.mp3", mimetype="audio/mpeg")
    content.save("output.mp3")
    ```

    #### Add extra metadata

    ```python
    content = Content(data, extra={"resolution": "1920x1080"})
    print(content.metadata["resolution"])
    ```

    #### Use `Content` with `Annotated`

    Weave supports using `Content` inside op signatures via `Annotated`, which lets the framework infer content types or validate MIME hints. Under the hood, Weave parses annotations like `Content["pdf"]` or `Content["application/pdf"]` using regex.

    ##### Without a type hint

    ```python
    @weave.op
    def read_image(path: Annotated[str, Content]) -> Annotated[bytes, Content]:
        return Path(path).read_bytes()
    ```

    ##### With a type hint

    ```python
    @weave.op
    def read_pdf(path: Annotated[str, Content[Literal["pdf"]]]) -> Annotated[bytes, Content[Literal["application/pdf"]]]:
        return Path(path).read_bytes()
    ```

    In each case, the output is displayed in the Weave UI (e.g., rendered image, audio player, etc.).

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
  This feature is not yet available in TypeScript.
  </TabItem>
</Tabs>
