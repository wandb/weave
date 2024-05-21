import * as Switch from '@radix-ui/react-switch';
import React from 'react';
import {twMerge} from 'tailwind-merge';

export type SwitchSize = 'small' | 'medium';
export const Root = ({
  className,
  size = 'medium',
  ...props
}: React.ComponentProps<typeof Switch.Root> & {size?: SwitchSize}) => (
  <Switch.Root
    className={twMerge(
      'flex items-center rounded-[12px] p-[1px] transition-colors duration-100 ease-out',
      'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
      props.checked ? ' bg-teal-500' : 'bg-moon-350',
      size === 'small' ? 'h-[16px] w-[28px]' : 'h-[24px] w-[44px]',
      className
    )}
    {...props}
  />
);

export const Thumb = ({
  className,
  size = 'medium',
  ...props
}: React.ComponentProps<typeof Switch.Thumb> & {
  checked: boolean;
  size?: SwitchSize;
}) => (
  <Switch.Thumb
    className={twMerge(
      'rounded-full bg-white transition-transform duration-100 ease-out',
      size === 'small' ? 'h-[14px] w-[14px]' : 'h-[22px] w-[22px]',
      size === 'small' && props.checked ? 'translate-x-12' : '',
      size === 'medium' && props.checked ? 'translate-x-20' : '',
      !props.checked && 'translate-x-0',
      className
    )}
    {...props}
  />
);
