/**
 * A small colored pill indicating the delta between two numbers,
 * allowing cycling between different representations such as absolute
 * or percentage difference.
 */

import React, {useState} from 'react';

import {Pill, TagColorName} from '../../../../Tag';
import {Tooltip} from '../../../../Tooltip';

type CompareGridPillNumberProps = {
  value: any;
  valueType: any;
  compareValue: any;
  compareValueType: any;
};

export const CompareGridPillNumber = ({
  value,
  compareValue,
}: CompareGridPillNumberProps) => {
  const [diffModeIdx, setDiffModeIdx] = useState(0);
  const difference = value - compareValue;
  const isIncrease = difference > 0;
  const modes = ['absolute', 'percentage'];
  if (compareValue !== 0 && isIncrease) {
    modes.push('ratio');
  }
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
    const percentage =
      compareValue !== 0 ? (difference / compareValue) * 100 : NaN;
    const percentageStr =
      percentage > 100
        ? Math.trunc(percentage).toLocaleString()
        : percentage.toFixed(2);
    pillColor = isIncrease ? 'green' : 'red';
    pillText = `${percentageStr}%`;
  } else if (mode === 'ratio') {
    const ratio =
      compareValue !== 0
        ? `${(value / compareValue).toFixed(1)}x`
        : 'undefined';
    pillColor = 'green';
    pillText = ratio;
  }

  return (
    <Tooltip
      trigger={
        <span className="cursor-pointer select-none" onClick={onClick}>
          <Pill color={pillColor} label={pillText} />
        </span>
      }
      content="Click to change comparison mode"
    />
  );
};
