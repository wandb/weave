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

## Files (PDFs, CSVs)

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
  
  ### PDFs
  You can log and visualize various file types like [PDFs](#pdfs) and [CSVs](#csvs) using the `weave.File` object. This includes PDFs with varying lengths or content. Weave captures file metadata like path, MIME type, and size in traces. You can also [preview](#preview-a-file) or [download](#download-a-file) traced files from the **Traces** tab.

  ```python
  import weave
  from pathlib import Path

  weave.init("pdf-example")

  @weave.op
  def return_file_pdf() -> weave.File:
      # Returns a PDF file "example.pdf" as a Weave file object.
      # Modify the filename/path as needed
      file_path = Path(__file__).parent.resolve() / "assets" / "example.pdf"
      return weave.File(file_path)

  @weave.op
  def accept_file_pdf(val: weave.File) -> str:
      # Accepts a Weave file object and prints metadata to the trace.
      # Useful for debugging or file inspection in ops.
      print("Path:", val.path)
      print("MIME type:", val.mimetype)
      print("Size:", val.size)
      return f"File size: {val.size}"

  # Run the file through the accept_file_pdf function to inspect it
  accept_file_pdf(return_file_pdf())
  ```
   
  ![Trace view of `accept_file_pdf`](imgs/accept-file-pdf.png)

  You can also work with multi-page PDFs:
  
  ```python
  @weave.op
  def return_file_pdf_many_pages() -> weave.File:
      # Similar to the above, but returns a multi-page PDF as a Weave file object.
      # Replace the file path with your own multi-page document.
      file_path = Path(__file__).parent.resolve() / "assets" / "example-many-pages.pdf"
      return weave.File(file_path)

  @weave.op
  def accept_file_pdf_many_pages(val: weave.File) -> str:
      # Upload and trace a multi-page PDF file in Weave and log its metadata.
      print("Path:", val.path)
      print("MIME type:", val.mimetype)
      print("Size:", val.size)
      return f"File size: {val.size}"

  accept_file_pdf_many_pages(return_file_pdf_many_pages())
  ```

  ### CSVs
  Similarly, you can log and work with CSV files using `weave.File`. This is useful for inspecting tabular data inputs.

  ```python
  import weave
  from pathlib import Path

  weave.init("csv-example")
  
  @weave.op
  def return_file_csv() -> weave.File:
      # Returns a CSV file as a Weave file object.
      # Replace the path if you want to use your own CSV.
      file_path = Path(__file__).parent.resolve() / "assets" / "example.csv"
      return weave.File(file_path)

  @weave.op
  def accept_file_csv(val: weave.File) -> str:
      # Prints metadata for a CSV file trace in Weave and returns its size as a string.
      print("Path:", val.path)
      print("MIME type:", val.mimetype)
      print("Size:", val.size)
      return f"File size: {val.size}"

  accept_file_csv(return_file_csv())
  ```

  This allows you to trace, inspect, and optionally process CSVs as part of your pipeline.

  ![Trace view of `accept_file_csv`](imgs/accept-file-csv.png)
  
  ### Download a file
  To download the file from the **Traces** tab, do the following:

  1. In the **Traces** tab, select the trace for the uploaded file (e.g. **accept_file_pdf**).

     ![Preview or download a file from the Traces tab](imgs/pdf-preview-download.png)
     
  2. To the right of the filename, click the download button. Your file is downloaded to your device.

  ### Preview a file

  To preview the file from the **Traces** tab, do the following:

  1. In the **Traces** tab, select the trace for the uploaded file (e.g. **accept_file_pdf**).

     ![Preview or download a file from the Traces tab](imgs/pdf-preview-download.png)
     
  2. To the left of the filename, click the icon or filename. A preview of the file displays in Weave.
  3. To close the preview, click the `X` in the upper right hand corner.
  
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
  This feature is not yet available in TypeScript.
  </TabItem>
  
</Tabs>
