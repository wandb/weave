import * as ToggleGroup from '@radix-ui/react-toggle-group';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Button} from '../Button';
import {IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {ToggleButtonGroupSize} from './types';

export type ToggleButtonGroupProps = {
  options: string[];
  value: string;
  size: ToggleButtonGroupSize;
  isDisabled?: boolean;
  icons?: Array<IconName | undefined>;
  onValueChange: (value: string) => void;
};

export const ToggleButtonGroup = React.forwardRef<
  HTMLDivElement,
  ToggleButtonGroupProps
>(({options, value, size, isDisabled = false, icons, onValueChange}, ref) => {
  if (options.length < 2) {
    console.error('ToggleButtonGroup requires at least two options.');
  }

  const handleValueChange = (newValue: string) => {
    if (newValue !== value) {
      onValueChange(newValue);
    }
  };
  return (
    <Tailwind>
      <ToggleGroup.Root
        type="single"
        value={value}
        onValueChange={handleValueChange}
        className="flex gap-px"
        ref={ref}>
        {options.map((option, index) => (
          <ToggleGroup.Item
            key={option}
            value={option}
            active={value === option}
            disabled={isDisabled}>
            <Button
              icon={icons?.[index]}
              size={size}
              className={twMerge(
                size === 'small' && 'gap-2 px-6 py-3 text-sm',
                size === 'medium' && 'gap-3 px-10 py-4 text-base',
                size === 'large' && 'gap-2 px-12 py-8 text-base',
                isDisabled && 'pointer-events-none opacity-35',
                value === option
                  ? 'bg-teal-300/[0.48] text-teal-600 hover:bg-teal-300/[0.48]'
                  : 'hover:bg-oblivion/7 bg-oblivion/5 text-moon-600 hover:text-moon-800',
                'first:rounded-l-sm', // First button rounded left
                'last:rounded-r-sm' // Last button rounded right
              )}>
              {option}
            </Button>
          </ToggleGroup.Item>
        ))}
      </ToggleGroup.Root>
    </Tailwind>
  );
});

ToggleButtonGroup.displayName = 'ToggleButtonGroup';
