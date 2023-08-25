import classNames from 'classnames';
import React, {FC} from 'react';

import {Icon, IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {getTagColor, TagColorName} from './utils';

export type PillProps = {
  label: string;
  icon?: IconName;
  color?: TagColorName;
};
export const Pill: FC<PillProps> = ({label, icon, color}) => {
  return (
    <Tailwind>
      <div
        key={`pill-${label}`}
        className={classNames(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-2xl text-[14px]',
          icon ? 'pl-4 pr-7' : 'px-7',
          getTagColor(color)
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
        className={classNames(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-2xl',
          getTagColor(color)
        )}>
        <Icon className="m-4 h-14 w-14" name={icon} />
      </div>
    </Tailwind>
  );
};
