/**
 * A small colored pill indicating the delta between two values.
 */

import React from 'react';

import {monthRoundedTime} from '../../../../../common/util/time';
import {Pill} from '../../../../Tag';
import {
  isProbablyTimestampMs,
  isProbablyTimestampSec,
} from '../pages/CallPage/ValueViewNumberTimestamp';
import {CompareGridPillNumber} from './CompareGridPillNumber';

type CompareGridPillProps = {
  value: any;
  valueType: any;
  compareValue: any;
  compareValueType: any;
};

export const CompareGridPill = (props: CompareGridPillProps) => {
  const {value, valueType, compareValue, compareValueType} = props;
  if (valueType !== 'number' || compareValueType !== 'number') {
    return null;
  }
  if (value === compareValue) {
    return null;
  }
  if (isProbablyTimestampMs(value) && isProbablyTimestampMs(compareValue)) {
    const difference = value - compareValue;
    const formatted = monthRoundedTime(Math.abs(difference / 1000));
    const color = difference > 0 ? 'green' : 'red';
    return <Pill color={color} label={formatted} />;
  }
  if (isProbablyTimestampSec(value) && isProbablyTimestampSec(compareValue)) {
    const difference = value - compareValue;
    const formatted = monthRoundedTime(Math.abs(difference));
    const color = difference > 0 ? 'green' : 'red';
    return <Pill color={color} label={formatted} />;
  }
  return <CompareGridPillNumber {...props} />;
};
