import * as ToggleGroup from '@radix-ui/react-toggle-group';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Button, ButtonSize} from './Button';
import {IconName} from './Icon';
import {Tailwind} from './Tailwind';
import {Tooltip} from './Tooltip';

export type ToggleOption = {
  value: string;
  icon?: IconName;
  isDisabled?: boolean;
  iconOnly?: boolean;
  tooltip?: string;
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
        className="flex gap-px"
        ref={ref}>
        {options.map(
          ({
            value: optionValue,
            icon,
            isDisabled: optionIsDisabled,
            tooltip,
            iconOnly = false,
          }) => {
            const button = (
              <Button
                icon={icon}
                size={size}
                onClick={() => handleValueChange(optionValue)}
                className={twMerge(
                  'night-aware',
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
                    ? 'bg-teal-300/[0.48] text-teal-600 hover:bg-teal-300/[0.48] dark:bg-teal-700/[0.48] dark:text-teal-400'
                    : 'hover:bg-oblivion/7 bg-oblivion/5 text-moon-600 hover:text-moon-800 dark:bg-moonbeam/[0.05] hover:dark:bg-teal-700/[0.48] hover:dark:text-teal-400',
                  'rounded-none group-first:rounded-l-sm group-first:rounded-r-none group-last:rounded-l-none group-last:rounded-r-sm'
                )}>
                {!iconOnly ? optionValue : <></>}
              </Button>
            );

            return (
              <div className="group" key={optionValue}>
                <ToggleGroup.Item
                  key={optionValue}
                  value={optionValue}
                  disabled={isDisabled}
                  asChild>
                  {tooltip ? (
                    <Tooltip content={tooltip} trigger={button} size="small" />
                  ) : (
                    button
                  )}
                </ToggleGroup.Item>
              </div>
            );
          }
        )}
      </ToggleGroup.Root>
    </Tailwind>
  );
});

ToggleButtonGroup.displayName = 'ToggleButtonGroup';
