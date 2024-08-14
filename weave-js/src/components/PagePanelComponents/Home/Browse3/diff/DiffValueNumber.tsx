/**
 * Compare two timestamp values.
 */

import React, {useState} from 'react';

import {Pill, TagColorName} from '../../../../Tag';
import {CellValue} from '../../Browse2/CellValue';
import {ARROW} from './DiffValueCommon';

type DiffValueNumberProps = {
  left: number;
  right: number;
};

export const DiffValueNumber = ({left, right}: DiffValueNumberProps) => {
  const difference = right - left;

  const isIncrease = right > left;
  const modes = ['absolute', 'percentage'];
  if (left !== 0 && isIncrease) {
    modes.push('ratio');
  }
  const [diffModeIdx, setDiffModeIdx] = useState(0);
  const mode = modes[diffModeIdx];

  const onClick = () => {
    setDiffModeIdx((diffModeIdx + 1) % modes.length);
  };
  let pillText = '';
  let pillColor: TagColorName = 'moon';
  if (mode === 'absolute') {
    const sign = isIncrease ? '+' : '';
    pillColor = isIncrease ? 'green' : 'red';
    pillText = `${sign}${difference.toLocaleString()}`;
  } else if (mode === 'percentage') {
    const percentage = left !== 0 ? (difference / left) * 100 : NaN;
    const percentageStr =
      percentage > 100
        ? Math.trunc(percentage).toLocaleString()
        : percentage.toFixed(2);
    pillColor = isIncrease ? 'green' : 'red';
    pillText = `${percentageStr}%`;
  } else if (mode === 'ratio') {
    const ratio = left !== 0 ? `${(right / left).toFixed(1)}x` : 'undefined';
    pillColor = 'green';
    pillText = ratio;
  }

  return (
    <div className="flex gap-4">
      <CellValue value={left} /> {ARROW} <CellValue value={right} />
      <span className="cursor-pointer" onClick={onClick}>
        <Pill color={pillColor} label={pillText} />
      </span>
    </div>
  );
};
