export const IMAGE_FILE_EXTENSIONS = [
  'jpg',
  'jpeg',
  'png',
  'tiff',
  'tif',
  'gif',
];

export const inputType = {
  type: 'union' as const,
  members: IMAGE_FILE_EXTENSIONS.map(ext => ({
    type: 'file' as const,
    extension: ext,
  })),
};
