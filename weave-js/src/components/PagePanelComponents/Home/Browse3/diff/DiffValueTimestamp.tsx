/**
 * Compare two timestamp values.
 */

import React from 'react';

import {monthRoundedTime} from '../../../../../common/util/time';
import {Pill} from '../../../../Tag';
import {Timestamp} from '../../../../Timestamp';
import {isProbablyTimestampMs} from '../pages/CallPage/ValueViewNumberTimestamp';
import {ARROW} from './DiffValueCommon';

type DiffValueTimestampProps = {
  left: number;
  right: number;
};

export const DiffValueTimestamp = ({left, right}: DiffValueTimestampProps) => {
  const leftS = isProbablyTimestampMs(left) ? left / 1000 : left;
  const rightS = isProbablyTimestampMs(right) ? right / 1000 : right;
  const difference = monthRoundedTime(Math.abs(rightS - leftS));
  const color = right - left > 0 ? 'green' : 'red';
  return (
    <div className="flex gap-4">
      <Timestamp value={leftS} /> {ARROW} <Timestamp value={rightS} />
      <Pill color={color} label={difference} />
    </div>
  );
};
