import * as RadixSwitch from '@radix-ui/react-switch';
import React from 'react';
import {twMerge} from 'tailwind-merge';

export type SwitchSize = 'small' | 'large';
export type SwitchMode = 'light' | 'dark';

export type SwitchProps = Omit<
  RadixSwitch.SwitchProps,
  'defaultChecked' | 'checked'
> & {
  checked: boolean;
  size?: SwitchSize;
  mode?: SwitchMode;
};

export const Switch = ({
  checked,
  className,
  size = 'small',
  mode = 'light',
  ...props
}: SwitchProps) => {
  const isSmall = size === 'small';
  const isLightMode = mode === 'light';
  return (
    <RadixSwitch.Root
      className={twMerge(
        'flex items-center p-[1px] transition-colors duration-100 ease-out',
        isSmall
          ? 'h-[16px] w-[28px] rounded-[14px]'
          : 'h-[24px] w-[44px] rounded-[22px]',
        'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
        checked ? 'bg-teal-500' : isLightMode ? 'bg-moon-350' : 'bg-moon-650',
        className
      )}
      {...props}>
      <RadixSwitch.Thumb
        className={twMerge(
          'rounded-full bg-white transition-transform duration-100 ease-out',
          isSmall
            ? 'h-[14px] w-[14px] rounded-[14px]'
            : 'h-[22px] w-[22px] rounded-[22px]',
          checked
            ? isSmall
              ? 'translate-x-12'
              : 'translate-x-20'
            : 'translate-x-0',
          className
        )}
        {...props}
      />
    </RadixSwitch.Root>
  );
};
