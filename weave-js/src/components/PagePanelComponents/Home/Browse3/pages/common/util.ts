import _ from 'lodash';
import React from 'react';

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
