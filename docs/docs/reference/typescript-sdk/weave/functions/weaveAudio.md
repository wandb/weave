[**weave**](../README.md)

***

[weave](../README.md) / weaveAudio

# Function: weaveAudio()

> **weaveAudio**(`options`): [`WeaveAudio`](../interfaces/WeaveAudio.md)

Defined in: [media.ts:62](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/media.ts#L62)

Create a new WeaveAudio object

## Parameters

### options

`WeaveAudioInput`

The options for this media type
   - data: The raw audio data as a Buffer
   - audioType: (Optional) The type of audio file, currently only 'wav' is supported

## Returns

[`WeaveAudio`](../interfaces/WeaveAudio.md)

## Example

```ts
const audioBuffer = fs.readFileSync('path/to/audio.wav');
const weaveAudio = weaveAudio({ data: audioBuffer });
```
