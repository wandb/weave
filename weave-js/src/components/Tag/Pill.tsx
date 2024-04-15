import React, { FC } from 'react';
import { twMerge } from 'tailwind-merge';

import { Icon, IconName } from '../Icon';
import { Tailwind } from '../Tailwind';
import * as PillAnatomy from './PillAnatomy';
import { getTagColorClass,TagColorName } from './utils';

export type PillProps = {
  label?: string;
  icon?: IconName;
  color?: TagColorName;
  className?: string;
};
export const Pill: FC<PillProps> = ({label, icon, color, className}) => {
  if (label && label.length > 0) {
    return (
      <PillAnatomy.Root
        color={color}
        className={twMerge(icon ? 'pl-4 pr-7' : 'px-7', className)}>
        {icon && <PillAnatomy.Indicator icon={icon} />}
        <PillAnatomy.Label text={label} />
      </PillAnatomy.Root>
    );
  }

  if (icon == null) {
    return null;
  }

  // icon-only pill
  return (
    <PillAnatomy.Root color={color} className={className}>
      <PillAnatomy.Indicator icon={icon} />
    </PillAnatomy.Root>
  );
};

export type IconOnlyPillProps = {
  icon: IconName;
  color?: TagColorName;
};
/** @deprecated */
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
