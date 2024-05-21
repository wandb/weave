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

const SWITCH_SIZE_STYLES = {
  small: 'h-[16px] w-[28px] rounded-[14px]',
  large: 'h-[24px] w-[44px] rounded-[22px]',
};

const SWITCH_MODE_STYLES = {
  light: 'bg-moon-350',
  dark: 'bg-moon-650',
};

const SWITCH_THUMB_STYLES = {
  small: 'h-[14px] w-[14px] rounded-[14px]',
  large: 'h-[22px] w-[22px] rounded-[22px]',
};

const SWITCH_THUMB_TRANSITION = {
  small: 'translate-x-12',
  large: 'translate-x-20',
};

export const Switch = ({
  checked,
  className,
  size = 'small',
  mode = 'light',
  ...props
}: SwitchProps) => (
  <RadixSwitch.Root
    className={twMerge(
      'flex items-center p-[1px] transition-colors duration-100 ease-out',
      'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
      SWITCH_SIZE_STYLES[size],
      checked ? 'bg-teal-500' : SWITCH_MODE_STYLES[mode],
      className
    )}
    {...props}>
    <RadixSwitch.Thumb
      className={twMerge(
        'rounded-full bg-white transition-transform duration-100 ease-out',
        SWITCH_THUMB_STYLES[size],
        checked ? SWITCH_THUMB_TRANSITION[size] : 'translate-x-0',
        className
      )}
      {...props}
    />
  </RadixSwitch.Root>
);
