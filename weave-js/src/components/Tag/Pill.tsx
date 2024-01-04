import React, {FC} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {getTagColorClass, TagColorName} from './utils';

export type PillProps = {
  label: string;
  icon?: IconName;
  color?: TagColorName;
  className?: string;
};
export const Pill: FC<PillProps> = ({label, icon, color, className}) => {
  return (
    <Tailwind>
      <div
        key={`pill-${label}`}
        className={twMerge(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-2xl text-[14px]',
          icon ? 'pl-4 pr-7' : 'px-7',
          getTagColorClass(color),
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
};
export const IconOnlyPill: FC<IconOnlyPillProps> = ({icon, color}) => {
  return (
    <Tailwind>
      <div
        key={`pill-${icon}`}
        className={twMerge(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-2xl',
          getTagColorClass(color)
        )}>
        <Icon className="m-4 h-14 w-14" name={icon} />
      </div>
    </Tailwind>
  );
};
