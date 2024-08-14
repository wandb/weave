import _ from 'lodash';

import {ObjectPath} from '../pages/CallPage/traverse';
import {isProbablyTimestamp} from '../pages/CallPage/ValueViewNumberTimestamp';
import {isWeaveRef} from '../filters/common';

type ValueType =
  | 'undefined'
  | 'null'
  | 'boolean'
  | 'string'
  | 'ref'
  | 'number'
  | 'timestamp'
  | 'other';

const determineType = (value: any): ValueType => {
  if (value === null) {
    return 'null';
  }
  if (value === undefined) {
    return 'undefined';
  }
  if (typeof value === 'boolean') {
    return 'boolean';
  }
  if (typeof value === 'string') {
    if (isWeaveRef(value)) {
      return 'ref';
    }
    return 'string';
  }
  if (typeof value === 'number') {
    return 'number';
  }
  return 'other';
};

export const computePanels = (
  objectType: string,
  path: ObjectPath,
  left: any,
  right: any
): string[] => {
  if (_.isEqual(left, right)) {
    return [];
  }
  const panels = [];
  const typeLeft = determineType(left);
  const typeRight = determineType(right);

  if (typeLeft === 'undefined' && typeRight === 'undefined') {
    return [];
  }

  if (typeLeft === typeRight) {
    if (isProbablyTimestamp(left) && isProbablyTimestamp(right)) {
      panels.push('Timestamp');
    }
    if (typeLeft === 'number') {
      panels.push('Number');
    }
    if (typeLeft === 'string') {
      if (left.length > 50 || right.length > 50) {
        panels.push('LongStringUnified');
        panels.push('LongStringSideBySide');
      }
      panels.push('StringLines');
      panels.push('StringWords');
      panels.push('StringChars');
    }
  }
  panels.push('SideBySide');
  return panels;
};
