import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Logging media

W&B Weave supports logging and has dedicated displays for numerous content types such as videos, images, audio files, PDFs, CSVs and HTML.

## Content API

The Content API handles media objects in Weave. Instead of using specific modules and classes like `PIL.Image` or `moviepy.VideoFileClip`, using the Content API allows you to import content into Weave as base64 data, file paths, raw bytes, or text.

The Content API introduces special handlers in the web app for media types that don't have legacy API handlers, such as PDF and HTML files. For media with pre-existing support in Weave (such as MP3, MP4, or PNG files), your data will display identically in the web app regardless of which API you use, however, for certain large file types like videos, using the Content API provides significant performance improvements.



:::note
The Content API is only available in Python.
:::

### Usage

There are two primary ways to use the Content API: type annotations and direct initialization.

Type annotations automatically detect the proper constructor to use, while direct initialization provides more fine-grained control and lets you take advantage of runtime features of the Content API in your code.

### Type Annotations

The Weave Content API is designed to primarily be used through type annotations, which signal to Weave that traced inputs and outputs should be processed and stored as content blobs.

```python
import weave
from weave import Content
from pathlib import Path
from typing import Annotated

@weave.op
def content_annotation(path: Annotated[str, Content]) -> Annotated[bytes, Content]:
    data = Path(path).read_bytes()
    return data

# Both input and output will show up as an MP4 file in Weave
# Input is a string and return value is bytes
bytes_data = content_annotation('./path/to/your/file.mp4')
```

### Direct Initialization

If you want to take advantage of features such as:
- Opening a file with a default application (such as a PDF viewer)
- Dumping the model to JSON to upload to your own blob storage (such as S3)
- Passing custom metadata to associate with the Content blob (such as the model used to generate it)

You can initialize content directly from your target type using one of the following methods:
- `Content.from_path` - Create from a file path
- `Content.from_bytes` - Create from raw bytes
- `Content.from_text` - Create from text string
- `Content.from_base64` - Create from base64-encoded data

```python
import weave
from weave import Content

@weave.op
def content_initialization(path: str) -> Content:
    return Content.from_path(path)

# Input shows up as path string and output as PDF file in Weave
content = content_initialization('./path/to/your/file.pdf')

content.open()  # Opens the file in your PDF viewer
content.model_dump()  # Dumps the model attributes to JSON
```

### Custom Mimetypes

Weave can detect most binary mimetypes, but custom mimetypes and text documents such as markdown may not be automatically detected, requiring you to manually specify the mimetype or extension of your file.

#### Custom Mimetypes with Type Annotations
```python
import weave
from weave import Content
from pathlib import Path
from typing import Annotated, Literal

@weave.op
def markdown_content(
    path: Annotated[str, Content[Literal['md']]]
) -> Annotated[str, Content[Literal['text/markdown']]]:
    return Path(path).read_text()

markdown_content('path/to/your/document.md')
```

#### Custom Mimetypes with Direct Initialization

```python
video_bytes = Path('/path/to/video.mp4').read_bytes()

# Pass an extension such as 'mp4' or '.mp4' to the extension parameter
# (not available for `from_path`)
content = Content.from_bytes(video_bytes, extension='.mp4')

# Pass a mimetype such as 'video/mp4' to the mimetype parameter
content = Content.from_bytes(video_bytes, mimetype='video/mp4')
```

### Properties

| Property    | Type             | Description                             |
| ----------- | ---------------- | --------------------------------------- |
| `data`      | `bytes`          | Raw binary content                      |
| `metadata`  | `dict[str, Any]` | Custom metadata dictionary              |
| `size`      | `int`            | Size of content in bytes                |
| `filename`  | `str`            | Extracted or provided filename          |
| `extension` | `str`            | File extension (e.g., `"jpg"`, `"mp3"`) |
| `mimetype`  | `str`            | MIME type (e.g., `"image/jpeg"`)        |
| `path`      | `str \| None`    | Source file path, if applicable         |
| `digest`    | `str`            | SHA256 hash of the content              |

### Methods

- `save(dest: str | Path) -> None`: Save content to a file
- `open() -> bool`: Open file using system default application (requires the content to have been saved or loaded from a path)
- `as_string() -> str`: Display the data as a string (bytes are decoded using the encoding attribute)

### Creation Methods

#### `Content.from_path(path, mimetype=None, metadata=None)`

Create Content from a file path:

```python
content = Content.from_path("assets/photo.jpg")
print(content.mimetype, content.size)
```

#### `Content.from_bytes(data, extension=None, mimetype=None, metadata=None)`

Create Content from raw bytes:

```python
content = Content.from_bytes(
    data_bytes,
    filename="audio.mp3", 
    mimetype="audio/mpeg"
)
content.save("output.mp3")
```

#### `Content.from_text(text, extension=None, mimetype=None, metadata=None)`

Create Content from text:

```python
content = Content.from_text("Hello, World!", mimetype="text/plain")
```

#### `Content.from_base64(b64_data, extension=None, mimetype=None, metadata=None)`

Create Content from base64-encoded data:

```python
content = Content.from_base64(base64_string)
print(content.metadata)
```

### Adding Custom Metadata

You can attach custom metadata to any Content object:

```python
content = Content.from_bytes(
    data,
    metadata={"resolution": "1920x1080", "model": "dall-e-3" }
)
print(content.metadata["resolution"])
```

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
