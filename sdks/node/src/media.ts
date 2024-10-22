// Define WeaveImage type
type WeaveImageInput = {
  data: Buffer;
  imageType: 'png';
};

interface WeaveImage extends WeaveImageInput {
  _weaveType: 'Image';
}

export function weaveImage({ data, imageType }: WeaveImageInput): WeaveImage {
  return {
    _weaveType: 'Image',
    data,
    imageType,
  };
}

// Function to check if a value is a WeaveImage
export function isWeaveImage(value: any): value is WeaveImage {
  return value && value._weaveType === 'Image';
}

type WeaveAudioInput = {
  data: Buffer;
  audioType: 'wav';
};

interface WeaveAudio extends WeaveAudioInput {
  _weaveType: 'Audio';
}

export function weaveAudio({ data, audioType }: WeaveAudioInput): WeaveAudio {
  return {
    _weaveType: 'Audio',
    data,
    audioType,
  };
}

export function isWeaveAudio(value: any): value is WeaveAudio {
  return value && value._weaveType === 'Audio';
}

type WeaveMedia = WeaveImage | WeaveAudio;

export function isMedia(value: any): value is WeaveMedia {
  return isWeaveImage(value) || isWeaveAudio(value);
}
