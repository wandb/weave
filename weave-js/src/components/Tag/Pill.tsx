import React, {FC} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {useTagClasses} from './Tag';
import {TagColorName} from './utils';

export type PillProps = {
  label: string;
  icon?: IconName;
  color?: TagColorName;
  className?: string;
  isInteractive?: boolean;
};
export const Pill: FC<PillProps> = ({
  label,
  icon,
  color,
  className,
  isInteractive,
}) => {
  const classes = useTagClasses({color, isInteractive});
  return (
    <Tailwind>
      <div
        key={`pill-${label}`}
        className={twMerge(
          classes,
          'rounded-2xl',
          icon ? 'pl-4 pr-7' : 'px-7',
          className
        )}>
        {icon && <Icon className="mr-4 h-14 w-14" name={icon} />}
        <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
          {label}
        </span>
      </div>
    </Tailwind>
  );
};

export type IconOnlyPillProps = {
  icon: IconName;
  color?: TagColorName;
  isInteractive?: boolean;
};
export const IconOnlyPill: FC<IconOnlyPillProps> = ({
  icon,
  color,
  isInteractive,
}) => {
  const classes = useTagClasses({color, isInteractive});
  return (
    <Tailwind>
      <div key={`pill-${icon}`} className={twMerge(classes, 'rounded-2xl')}>
        <Icon className="m-4 h-14 w-14" name={icon} />
      </div>
    </Tailwind>
  );
};
