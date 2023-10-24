import React from 'react';
import * as Switch from '@radix-ui/react-switch';
import {twMerge} from 'tailwind-merge';

export const Root = ({
  className,
  ...props
}: React.ComponentProps<typeof Switch.Root>) => (
  <Switch.Root
    className={twMerge(
      'flex h-[24px] w-[44px] items-center rounded-[12px] p-[1px] transition-colors duration-100 ease-out',
      'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
      props.checked ? ' bg-teal-500' : 'bg-moon-350',
      className
    )}
    {...props}
  />
);

export const Thumb = ({
  className,
  ...props
}: React.ComponentProps<typeof Switch.Thumb> & {checked: boolean}) => (
  <Switch.Thumb
    className={twMerge(
      'h-[22px] w-[22px] rounded-full bg-white transition-transform duration-100 ease-out',
      props.checked ? 'translate-x-20' : 'translate-x-0',
      className
    )}
    {...props}
  />
);
