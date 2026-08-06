export const DEFAULT_IMAGE_TYPE = 'png';
export const DEFAULT_AUDIO_TYPE = 'wav';

export type ImageType = 'png' | 'jpeg' | 'webp';
export type AudioType = 'wav';

// Define WeaveImage type
type WeaveImageInput = {
  data: Buffer;
  imageType?: ImageType;
};

export interface WeaveImage extends WeaveImageInput {
  _weaveType: 'Image';
}

/**
 * Create a new WeaveImage object
 *
 * @param options The options for this media type
 *    - data: The raw image data as a Buffer
 *    - imageType: (Optional) The image format: 'png' (default), 'jpeg' or 'webp'.
 *      Publishing always names the stored file image.png
 *
 * @example
 * const imageBuffer = fs.readFileSync('path/to/image.png');
 * const weaveImage = weaveImage({ data: imageBuffer });
 */
export function weaveImage({data, imageType}: WeaveImageInput): WeaveImage {
  const resolvedImageType = imageType ?? DEFAULT_IMAGE_TYPE;
  return {
    _weaveType: 'Image',
    data,
    imageType: resolvedImageType,
  };
}

// Mirrors ext_to_pil_format in weave/type_handlers/Image/image.py; the label is
// MIME spelling, so a stored `jpg` reads back as `jpeg`.
const IMAGE_TYPE_BY_EXTENSION = new Map<string, ImageType>([
  ['png', 'png'],
  ['jpg', 'jpeg'],
  ['webp', 'webp'],
]);

/**
 * Read the image format off a stored file name, e.g. `image.jpg` -> `jpeg`.
 * Returns undefined for an extension we do not know, so the caller keeps the
 * default format.
 */
export function imageTypeFromFileName(fileName: string): ImageType | undefined {
  return IMAGE_TYPE_BY_EXTENSION.get(
    fileName.slice(fileName.lastIndexOf('.') + 1)
  );
}

// Function to check if a value is a WeaveImage
export function isWeaveImage(value: any): value is WeaveImage {
  return value && value._weaveType === 'Image';
}

type WeaveAudioInput = {
  data: Buffer;
  audioType?: AudioType;
};

export interface WeaveAudio extends WeaveAudioInput {
  _weaveType: 'Audio';
}

/**
 * Create a new WeaveAudio object
 *
 * @param options The options for this media type
 *    - data: The raw audio data as a Buffer
 *    - audioType: (Optional) The type of audio file, currently only 'wav' is supported
 *
 * @example
 * const audioBuffer = fs.readFileSync('path/to/audio.wav');
 * const weaveAudio = weaveAudio({ data: audioBuffer });
 */
export function weaveAudio({data, audioType}: WeaveAudioInput): WeaveAudio {
  const resolvedAudioType = audioType ?? DEFAULT_AUDIO_TYPE;
  return {
    _weaveType: 'Audio',
    data,
    audioType: resolvedAudioType,
  };
}

export function isWeaveAudio(value: any): value is WeaveAudio {
  return value && value._weaveType === 'Audio';
}

type WeaveMedia = WeaveImage | WeaveAudio;

export function isMedia(value: any): value is WeaveMedia {
  return isWeaveImage(value) || isWeaveAudio(value);
}
