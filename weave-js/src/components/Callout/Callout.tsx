import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import {getTagColorClass, type TagColorName} from '../Tag';
import {Tailwind} from '../Tailwind';
import {CalloutSize} from './types';

export type CalloutProps = {
  className?: string;
  color: TagColorName;
  icon: IconName;
  size: CalloutSize;
};

export const Callout = ({className, color, icon, size}: CalloutProps) => {
  return (
    <Tailwind>
      <div
        className={twMerge(
          'night-aware',
          getTagColorClass(color),
          'flex items-center justify-center rounded-full',
          size === 'x-small' && 'h-[40px] w-[40px]',
          size === 'small' && 'h-[48px] w-[48px]',
          size === 'medium' && 'h-[64px] w-[64px]',
          size === 'large' && 'h-[80px] w-[80px]',
          className
        )}>
        <Icon
          role="presentation"
          className={twMerge(
            size === 'x-small' && 'h-[20px] w-[20px]',
            size === 'small' && 'h-[24px] w-[24px]',
            size === 'medium' && 'h-[32px] w-[32px]',
            size === 'large' && 'h-[33px] w-[33px]'
          )}
          name={icon}
        />
      </div>
    </Tailwind>
  );
};
