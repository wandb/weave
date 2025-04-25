import {Icon} from '@wandb/weave/components/Icon';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import classNames from 'classnames';
import React from 'react';

type ViewNameProps = {
  value: string;
  onEditNameStart?: () => void;
  tooltip?: string;
};

export const ViewName = ({value, onEditNameStart, tooltip}: ViewNameProps) => {
  const canEditName = onEditNameStart != null;
  const onClick = () => {
    if (canEditName) {
      onEditNameStart();
    }
  };
  const body = (
    <div
      className={classNames(
        'group flex w-max items-center rounded-md px-8 py-4',
        {
          'cursor-pointer hover:bg-moon-100': canEditName,
        }
      )}
      onClick={onClick}>
      {value}
      {canEditName && (
        <Icon
          name="pencil-edit"
          width={16}
          height={16}
          className="ml-8 min-w-[16px] text-moon-500 opacity-0 group-hover:opacity-100"
        />
      )}
    </div>
  );
  if (tooltip) {
    return <Tooltip content={tooltip} trigger={body} noTriggerWrap />;
  }
  return body;
};
