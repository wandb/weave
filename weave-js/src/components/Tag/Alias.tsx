import React, {FC, ReactElement} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon} from '../Icon';
import {Tailwind} from '../Tailwind';
import {RemoveAction} from './RemoveAction';
import {useTagClasses} from './Tag';
import {TagColorName} from './utils';

export const DEFAULT_ALIAS_ICON = 'email-at';

export type AliasProps = {
  label: string;
  color?: TagColorName;
  showIcon?: boolean;
};
export const Alias: FC<AliasProps> = ({label, color, showIcon = false}) => {
  const classes = useTagClasses({color, label});
  return (
    <Tailwind>
      <div
        className={twMerge(
          classes,
          'font-mono text-[13px]',
          showIcon ? 'pl-4 pr-6' : 'px-6'
        )}>
        {showIcon && (
          <Icon
            role="presentation"
            className="mr-4 h-14 w-14"
            name={DEFAULT_ALIAS_ICON}
          />
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
  const classes = useTagClasses({color, label, isInteractive: true});
  return (
    <Tailwind>
      <div className={twMerge(classes, 'px-4 font-mono text-[13px]')}>
        {showIcon && (
          <Icon
            role="presentation"
            className="mr-4 h-14 w-14"
            name={DEFAULT_ALIAS_ICON}
          />
        )}
        <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
          {label}
        </span>
        {removeAction}
      </div>
    </Tailwind>
  );
};
