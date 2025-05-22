import {isWeaveObjectRef, parseRefMaybe} from '@wandb/weave/react';

import {OBJECT_ATTR_EDGE_NAME, TABLE_ID_EDGE_NAME} from './constants';

export const generateStableDigest = (obj: any): string => {
  if (obj === undefined || obj === null) {
    return 'null'; // Return consistent string for null/undefined
  }

  try {
    // Sort keys to ensure stable stringification
    const sortObjectKeys = (val: any): any => {
      if (val === null || val === undefined) {
        return null;
      }

      if (typeof val !== 'object' || Array.isArray(val)) {
        return val;
      }

      return Object.keys(val)
        .sort()
        .reduce((result: any, key) => {
          result[key] = sortObjectKeys(val[key]);
          return result;
        }, {});
    };

    return JSON.stringify(sortObjectKeys(obj));
  } catch (e) {
    // In case of any JSON serialization errors, return a fallback value
    console.warn('Error generating stable digest:', e);
    return `digest_${Date.now()}`;
  }
};

export const maybeExtractDatasetRowRefDigest = (value: any): string | null => {
  if (typeof value !== 'string') {
    return null;
  }
  const parsedMaybe = parseRefMaybe(value);
  if (parsedMaybe === null) {
    return null;
  }
  if (!isWeaveObjectRef(parsedMaybe)) {
    return null;
  }
  if (parsedMaybe.weaveKind !== 'object') {
    return null;
  }
  if (
    !(parsedMaybe.artifactRefExtra && parsedMaybe.artifactRefExtra.length === 4)
  ) {
    return null;
  }
  if (
    !(parsedMaybe.artifactRefExtra[0] === OBJECT_ATTR_EDGE_NAME) &&
    parsedMaybe.artifactRefExtra[1] === 'rows' &&
    parsedMaybe.artifactRefExtra[2] === TABLE_ID_EDGE_NAME
  ) {
    return null;
  }
  if (typeof parsedMaybe.artifactRefExtra[3] !== 'string') {
    return null;
  }
  return parsedMaybe.artifactRefExtra[3];
};
