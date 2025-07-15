/**
 * A small colored pill indicating the delta between two values.
 */

import React, {useState} from 'react';

import {Pill, TagColorName} from '../../../../Tag';
import {Tooltip} from '../../../../Tooltip';

type DiffPillProps = {
  value: any;
  compareValue: any;
  valueFormatter?: (value: any) => string;
  lowerIsBetter?: boolean;
};

export const DiffPill = ({
  value,
  compareValue,
  valueFormatter,
  lowerIsBetter,
}: DiffPillProps) => {
  const [diffModeIdx, setDiffModeIdx] = useState(0);
  const difference = value - compareValue;
  const isIncrease = difference > 0;
  const modes = ['absolute', 'percentage'];
  if (compareValue !== 0 && isIncrease) {
    modes.push('ratio');
  }
  const mode = modes[diffModeIdx];

  if (!valueFormatter) {
    valueFormatter = (value: any) => value.toLocaleString();
  }

  const onClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    setDiffModeIdx((diffModeIdx + 1) % modes.length);
  };
  let pillText = '';
  let pillColor: TagColorName = 'moon';
  if (mode === 'absolute') {
    const sign = isIncrease ? '+' : '';
    pillColor = isIncrease ? 'green' : 'red';
    pillText = `${sign}${valueFormatter?.(difference)}`;
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

  // Invert the colors if lower is better
  if (pillColor !== 'moon' && lowerIsBetter) {
    pillColor = pillColor === 'green' ? 'red' : 'green';
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
