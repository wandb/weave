import * as ToggleGroup from '@radix-ui/react-toggle-group';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Button} from '../Button';
import {IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {ToggleButtonGroupSizes} from './types';

export type ToggleOption = {
  label: string;
  icon?: IconName;
};

export type ToggleButtonGroupProps = {
  options: ToggleOption[];
  value: string;
  size: ToggleButtonGroupSizes;
  isDisabled?: boolean;
  onValueChange: (value: string) => void;
};

/**
 * ToggleButtonGroup component should only be rendered if options.length >= 2.
 */
export const ToggleButtonGroup = React.forwardRef<
  HTMLDivElement,
  ToggleButtonGroupProps
>(({options, value, size, isDisabled = false, onValueChange}, ref) => {
  if (options.length < 2) {
    return null; // Do not render if there are fewer than two options
  }

  const handleValueChange = (newValue: string) => {
    if (newValue !== value) {
      onValueChange(newValue);
    }
  };
  return (
    <Tailwind>
      <ToggleGroup.Root
        type="single" // supports single selection only
        value={value}
        onValueChange={handleValueChange}
        className="flex gap-px"
        ref={ref}>
        {options.map(({label, icon}) => (
          <ToggleGroup.Item
            key={label}
            value={label}
            disabled={isDisabled || value === label}>
            <Button
              icon={icon}
              size={size}
              className={twMerge(
                size === 'small' && 'gap-2 px-6 py-3 text-sm',
                size === 'medium' && 'gap-3 px-10 py-4 text-base',
                size === 'large' && 'gap-2 px-12 py-8 text-base',
                isDisabled && 'pointer-events-none opacity-35',
                value === label
                  ? 'bg-teal-300/[0.48] text-teal-600 hover:bg-teal-300/[0.48]'
                  : 'hover:bg-oblivion/7 bg-oblivion/5 text-moon-600 hover:text-moon-800',
                'first:rounded-l-sm', // First button rounded left
                'last:rounded-r-sm' // Last button rounded right
              )}>
              {label}
            </Button>
          </ToggleGroup.Item>
        ))}
      </ToggleGroup.Root>
    </Tailwind>
  );
});

ToggleButtonGroup.displayName = 'ToggleButtonGroup';
