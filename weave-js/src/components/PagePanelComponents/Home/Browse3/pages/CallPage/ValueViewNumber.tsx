import React from 'react';

import {Tooltip} from '../../../../../Tooltip';

type ValueViewNumberProps = {
  value: number;
  fractionDigits?: number;
};

export const ValueViewNumber = ({
  value,
  fractionDigits,
}: ValueViewNumberProps) => {
  if (Number.isInteger(value)) {
    return <span>{value.toLocaleString()}</span>;
  }

  const str = value.toString();
  const fixed = value.toFixed(fractionDigits ?? 6);
  const node = <span>{fixed}</span>;
  if (str !== fixed) {
    return <Tooltip content={str} trigger={node} />;
  }
  return node;
};
