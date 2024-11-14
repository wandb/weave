import * as ToggleGroup from '@radix-ui/react-toggle-group';
import React from 'react';
import { twMerge } from 'tailwind-merge';
import {Tailwind} from '../Tailwind';
import {ToggleButtonGroupSize} from './types';

export type ToggleButtonGroupProps = {
  options: string[];
  value: string;
  onValueChange: (value: string) => void;
  size: ToggleButtonGroupSize;
};

export const ToggleButtonGroup = React.forwardRef<HTMLDivElement, ToggleButtonGroupProps>(
  ({ options, value, onValueChange, size }, ref) => {
    return (
      <Tailwind>
        <ToggleGroup.Root
          type="single"
          value={value}
          onValueChange={onValueChange}
          className="flex space-x-2"
          ref={ref}
        >
          {options.map((option) => (
            <ToggleGroup.Item
              key={option}
              value={option}
              className={twMerge(
                "inline-flex items-center justify-center whitespace-nowrap font-['Source_Sans_Pro'] font-semibold gap-[1px] my-12",
                size === 'small' && 'px-6 py-3 text-sm leading-[18px]',
                size === 'medium' && 'px-10 py-4 text-base leading-normal',
                size === 'large' && 'px-12 py-8 text-base leading-normal',
                value === option ? 'bg-[#a9edf2]/50 text-[#038194]' : 'bg-[#0d0f12]/5 text-[#565c66]',
                'first:rounded-l-sm', // First button rounded left
                'last:rounded-r-sm' // Last button rounded right
              )}
            >
              {option}
            </ToggleGroup.Item>
          ))}
        </ToggleGroup.Root>
      </Tailwind>
    );
  }
);

ToggleButtonGroup.displayName = 'ToggleButtonGroup';
