[**weave**](../README.md) • **Docs**

***

[weave](../README.md) / weaveAudio

# Function: weaveAudio()

> **weaveAudio**(`options`): `WeaveAudio`

Create a new WeaveAudio object

## Parameters

• **options**: `WeaveAudioInput`

The options for this media type
   - data: The raw audio data as a Buffer
   - audioType: (Optional) The type of audio file, currently only 'wav' is supported

## Returns

`WeaveAudio`

## Example

```ts
const audioBuffer = fs.readFileSync('path/to/audio.wav');
const weaveAudio = weaveAudio({ data: audioBuffer });
```

## Defined in

[media.ts:62](https://github.com/wandb/weave/blob/e2313369cb35bc1b6f97c70539926dd951ead21e/sdks/node/src/media.ts#L62)
