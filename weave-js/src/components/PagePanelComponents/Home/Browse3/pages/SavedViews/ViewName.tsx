import {Tooltip} from '@wandb/weave/components/Tooltip';
import React from 'react';

type ViewNameProps = {
  value: string;
  onEditNameStart: () => void;
  tooltip?: string;
};

export const ViewName = ({value, onEditNameStart, tooltip}: ViewNameProps) => {
  const onClick = () => {
    onEditNameStart();
  };
  const body = (
    <div className="hover:cursor-pointer hover:bg-moon-100" onClick={onClick}>
      {value}
    </div>
  );
  if (tooltip) {
    return <Tooltip content={tooltip} trigger={body} />;
  }
  return body;
};
