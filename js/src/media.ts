// Define WeaveImage type
interface WeaveImage {
  _weaveType: 'Image';
  data: Buffer;
  imageType: 'png';
}

export function weaveImage({
  data,
  imageType,
}: {
  data: Buffer;
  imageType: 'png';
}): WeaveImage {
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

export function isMedia(value: any): value is WeaveImage {
  return isWeaveImage(value);
}
