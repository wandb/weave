import classNames from 'classnames';
import React, {FC, ReactElement} from 'react';

import {Icon} from '../Icon';
import {Tailwind} from '../Tailwind';
import {RemoveAction} from './RemoveAction';
import {getTagColorClass, TagColorName} from './utils';

export const DEFAULT_ALIAS_ICON = 'email-at';

export type AliasProps = {
  label: string;
  color?: TagColorName;
  showIcon?: boolean;
};
export const Alias: FC<AliasProps> = ({label, color, showIcon = false}) => {
  return (
    <Tailwind>
      <div
        key={`pill-${label}`}
        className={classNames(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-[3px] font-mono text-[13px]',
          showIcon ? 'pl-4 pr-6' : 'px-6',
          getTagColorClass(color)
        )}>
        {showIcon && (
          <Icon className="mr-4 h-14 w-14" name={DEFAULT_ALIAS_ICON} />
        )}
        <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
          {label}
        </span>
      </div>
    </Tailwind>
  );
};

export type RemovableAliasProps = {
  label: string;
  removeAction: ReactElement<typeof RemoveAction>;
  color?: TagColorName;
  showIcon?: boolean;
};
export const RemovableAlias: FC<RemovableAliasProps> = ({
  label,
  removeAction,
  color,
  showIcon = false,
}) => {
  return (
    <Tailwind>
      <div
        key={`pill-${label}`}
        className={classNames(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-[3px] px-4 font-mono text-[13px]',
          getTagColorClass(color)
        )}>
        {showIcon && (
          <Icon className="mr-4 h-14 w-14" name={DEFAULT_ALIAS_ICON} />
        )}
        <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
          {label}
        </span>
        {removeAction}
      </div>
    </Tailwind>
  );
};
