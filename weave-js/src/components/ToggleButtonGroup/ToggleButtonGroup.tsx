import React from 'react';
import { twMerge } from 'tailwind-merge';
import * as ToggleGroup from '@radix-ui/react-toggle-group';

import {Icon, IconName} from '../Icon';
import {Button} from '../Button';
import {Tailwind} from '../Tailwind';
import {ToggleButtonGroupSize} from './types';

export type ToggleButtonGroupProps = {
  options: string[];
  value: string;
  size: ToggleButtonGroupSize;
  isDisabled?: boolean;
  icons?: (IconName | undefined)[];
  onValueChange: (value: string) => void;
};

export const ToggleButtonGroup = React.forwardRef<HTMLDivElement, ToggleButtonGroupProps>(
  ({ options, value, size, isDisabled, icons, onValueChange }, ref) => {
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
          className="flex gap-[1px] my-16"
          ref={ref}
        >
          {options.map((option, index) => (
            <ToggleGroup.Item
              key={option}
              value={option}
              active={value === option}
              disabled={isDisabled}
            >
              <Button
                icon={icons?.[index]}
                className={twMerge(
                "flex justify-center items-center",
                  size === 'small' && 'px-6 py-3 text-sm leading-[18px]',
                  size === 'medium' && 'px-10 py-4 text-base leading-normal',
                  size === 'large' && 'px-12 py-8 text-base leading-normal',
                  isDisabled && 'pointer-events-none opacity-35',
                  value === option 
                    ? 'bg-teal-300/[0.48] text-teal-600 hover:bg-teal-300/[0.48]' 
                    : 'bg-oblivion/5 text-[#565c66] hover:text-[#0d0f12] hover:bg-moonbeam/[0.05]',
                  'first:rounded-l-sm', // First button rounded left
                  'last:rounded-r-sm', // Last button rounded right
                  'gap-3'
                )}
              >
                {option}
              </Button>
            </ToggleGroup.Item>
          ))}
        </ToggleGroup.Root>
      </Tailwind>
    );
  }
);

ToggleButtonGroup.displayName = 'ToggleButtonGroup';
