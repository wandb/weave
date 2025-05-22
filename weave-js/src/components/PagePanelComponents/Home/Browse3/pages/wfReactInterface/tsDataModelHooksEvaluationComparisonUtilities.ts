import {isWeaveObjectRef, parseRefMaybe} from '@wandb/weave/react';

import {OBJECT_ATTR_EDGE_NAME, TABLE_ID_EDGE_NAME} from './constants';
import {TraceCallSchema} from './traceServerClientTypes';

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

export const calculatePredictAndScoreCallExampleDigest = (
  call: TraceCallSchema
): string => {
  const example = call.inputs.example;

  const maybeDigest = maybeExtractDatasetRowRefDigest(example);
  if (maybeDigest !== null) {
    return maybeDigest;
  }

  return generateStableDigest(example);
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
  const datasetRowPrefix = `${OBJECT_ATTR_EDGE_NAME}/rows/${TABLE_ID_EDGE_NAME}/`;
  if (!parsedMaybe.artifactRefExtra?.startsWith(datasetRowPrefix)) {
    return null;
  }
  return parsedMaybe.artifactRefExtra.slice(datasetRowPrefix.length);
};
