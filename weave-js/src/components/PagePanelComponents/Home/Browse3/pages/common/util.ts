import _ from 'lodash';
import React from 'react';

import {
  WANDB_ARTIFACT_REF_PREFIX,
  WEAVE_REF_PREFIX,
} from '../wfReactInterface/constants';

export const isPrimitive = (val: any) => {
  return (
    React.isValidElement(val) ||
    _.isString(val) ||
    _.isNumber(val) ||
    _.isBoolean(val) ||
    _.isDate(val) ||
    _.isNil(val)
  );
};

export const isRef = (value: any): boolean => {
  if (typeof value !== 'string') {
    return false;
  }
  if (
    value.startsWith(WANDB_ARTIFACT_REF_PREFIX) ||
    value.startsWith(WEAVE_REF_PREFIX)
  ) {
    return true;
  }
  return false;
};

// Convert a list of objects into an object where the keys are integers
// corresponding to the list indices and the values are the value of the
// list at that index.
export const listToObject = <T>(list: T[]): Record<number, T> => {
  const object: Record<number, T> = {};
  list.forEach((item, index) => {
    object[index] = item;
  });
  return object;
};
