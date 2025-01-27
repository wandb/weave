export const DEFAULT_IMAGE_TYPE = 'png';
export const DEFAULT_AUDIO_TYPE = 'wav';

export type ImageType = 'png';
export type AudioType = 'wav';

// Define WeaveImage type
type WeaveImageInput = {
  data: Buffer;
  imageType?: ImageType;
};

interface WeaveImage extends WeaveImageInput {
  _weaveType: 'Image';
}

/**
 * Create a new WeaveImage object
 *
 * @param options The options for this media type
 *    - data: The raw image data as a Buffer
 *    - imageType: (Optional) The type of image file, currently only 'png' is supported
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
