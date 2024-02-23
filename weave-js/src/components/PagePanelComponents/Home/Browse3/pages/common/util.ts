import _ from 'lodash';
import React from 'react';

export type Primitive =
  | string
  | number
  | boolean
  | Date
  | null
  | React.ReactElement;

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
