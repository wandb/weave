import * as ToggleGroup from '@radix-ui/react-toggle-group';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Button, ButtonSize} from './Button';
import {IconName} from './Icon';
import {Tailwind} from './Tailwind';

export type ToggleOption = {
  value: string;
  icon?: IconName;
  isDisabled?: boolean;
  iconOnly?: boolean;
};

export type ToggleButtonGroupProps = {
  options: ToggleOption[];
  value: string;
  size: ButtonSize;
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

  if (!options.some(option => option.value === value)) {
    console.warn(
      `Warning: The provided value "${value}" is not one of the options.`
    );
  }

  const handleValueChange = (newValue: string) => {
    if (
      newValue !== value &&
      options.find(option => option.value === newValue)?.isDisabled !== true
    ) {
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
        {options.map(
          ({
            value: optionValue,
            icon,
            isDisabled: optionIsDisabled,
            iconOnly = false,
          }) => (
            <ToggleGroup.Item
              key={optionValue}
              value={optionValue}
              disabled={isDisabled}
              asChild>
              <Button
                icon={icon}
                size={size}
                className={twMerge(
                  size === 'small' &&
                    (icon ? 'gap-4 px-4 py-3 text-sm' : 'px-8 py-3 text-sm'),
                  size === 'medium' &&
                    (icon
                      ? 'gap-5 px-7 py-4 text-base'
                      : 'px-10 py-4 text-base'),
                  size === 'large' &&
                    (icon
                      ? 'gap-6 px-10 py-8 text-base'
                      : 'px-12 py-8 text-base'),
                  (isDisabled || optionIsDisabled) && 'cursor-auto opacity-35',
                  value === optionValue
                    ? 'bg-teal-300/[0.48] text-teal-600 hover:bg-teal-300/[0.48]'
                    : 'hover:bg-oblivion/7 bg-oblivion/5 text-moon-600 hover:text-moon-800',
                  'first:rounded-l-sm', // First button rounded left
                  'last:rounded-r-sm' // Last button rounded right
                )}>
                {!iconOnly ? optionValue : <></>}
              </Button>
            </ToggleGroup.Item>
          )
        )}
      </ToggleGroup.Root>
    </Tailwind>
  );
});

ToggleButtonGroup.displayName = 'ToggleButtonGroup';
