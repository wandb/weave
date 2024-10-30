[**weave**](../README.md) • **Docs**

***

[weave](../globals.md) / weaveImage

# Function: weaveImage()

> **weaveImage**(`options`): `WeaveImage`

Create a new WeaveImage object

## Parameters

• **options**: `WeaveImageInput`

The options for this media type
   - data: The raw image data as a Buffer
   - imageType: (Optional) The type of image file, currently only 'png' is supported

## Returns

`WeaveImage`

## Example

```ts
const imageBuffer = fs.readFileSync('path/to/image.png');
const weaveImage = weaveImage({ data: imageBuffer });
```

## Defined in

[media.ts:28](https://github.com/wandb/weave/blob/f0de86a1943f1d5c6c828f42faab64acc924c307/sdks/node/src/media.ts#L28)
