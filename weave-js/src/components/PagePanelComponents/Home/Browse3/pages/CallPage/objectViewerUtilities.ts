/**
 * Helpers for detecting and patching base64 encoded image data in a known
 * JSON format (such as that expected by Anthropic's API) to render thumbnail
 * instead of string.
 */

import _ from 'lodash';

import {TraverseContext} from './traverse';

const SUPPORTED_IMAGE_TYPES = [
  'image/gif',
  'image/jpeg',
  'image/png',
  'image/webp',
];

// Check if dictionary contains base64 encoded image data with a known schema.
export const isKnownImageDictFormat = (value: Record<string, any>): boolean => {
  if (value.type === 'image' && _.isPlainObject(value.source)) {
    const source = value.source as Record<string, any>;
    if (
      source.type === 'base64' &&
      SUPPORTED_IMAGE_TYPES.includes(source.media_type) &&
      _.isString(source.data)
    ) {
      return true;
    }
  }
  return false;
};

// Return the replacement context rows for a detected image.
export const getKnownImageDictContexts = (
  context: TraverseContext
): TraverseContext[] => {
  const pathSource = context.path.plus('source');
  const mimetype = context.value.source.media_type;
  const data = `data:${mimetype};base64,${context.value.source.data}`;
  return [
    context,
    {
      depth: context.depth + 1,
      isLeaf: true,
      path: context.path.plus('type'),
      value: 'image',
      valueType: 'string',
    },
    {
      depth: context.depth + 2,
      isLeaf: false,
      path: pathSource,
      value: {
        type: 'base64',
        media_type: mimetype,
        data,
      },
      valueType: 'object',
    },
    {
      depth: context.depth + 3,
      isLeaf: true,
      path: pathSource.plus('type'),
      value: 'base64',
      valueType: 'string',
    },
    {
      depth: context.depth + 3,
      isLeaf: true,
      path: pathSource.plus('media_type'),
      value: mimetype,
      valueType: 'string',
    },
    {
      depth: context.depth + 3,
      isLeaf: true,
      path: pathSource.plus('data'),
      value: data,
      valueType: 'string',
    },
  ];
};
