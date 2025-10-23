[**weave**](../README.md)

***

[weave](../README.md) / weaveImage

# Function: weaveImage()

> **weaveImage**(`options`): [`WeaveImage`](../interfaces/WeaveImage.md)

Defined in: [media.ts:28](https://github.com/wandb/weave/blob/69f1caabebc727846756574d549b7e7dda458b63/sdks/node/src/media.ts#L28)

Create a new WeaveImage object

## Parameters

### options

`WeaveImageInput`

The options for this media type
   - data: The raw image data as a Buffer
   - imageType: (Optional) The type of image file, currently only 'png' is supported

## Returns

[`WeaveImage`](../interfaces/WeaveImage.md)

## Example

```ts
const imageBuffer = fs.readFileSync('path/to/image.png');
const weaveImage = weaveImage({ data: imageBuffer });
```
