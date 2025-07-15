import React from 'react';

import {Icon} from '../../../../Icon';
import {Tooltip} from '../../../../Tooltip';

type ModelComparisonRowHeaderProps = {
  label: string;
  labelSecondary?: string;
  tooltip?: string;
};

export const ModelComparisonRowHeader = ({
  label,
  labelSecondary,
  tooltip,
}: ModelComparisonRowHeaderProps) => {
  let body = (
    <div className="flex items-baseline gap-8">
      {label}
      {labelSecondary && (
        <div className="text-xs text-moon-500">{labelSecondary}</div>
      )}
    </div>
  );
  if (tooltip) {
    return (
      <Tooltip
        content={<div className="max-w-[300px]">{tooltip}</div>}
        trigger={body}
      />
    );
  }
  return body;
};
