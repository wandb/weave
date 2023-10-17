import * as RadixSlider from '@radix-ui/react-slider';
import React from 'react';
import {twMerge} from 'tailwind-merge';
import {Tailwind} from '../Tailwind';

export type SliderRootProps = React.ComponentProps<typeof RadixSlider.Root>;
export const Root = ({className, ...props}: SliderRootProps) => (
  <Tailwind>
    <RadixSlider.Root
      className={twMerge(
        'relative flex h-20 w-full touch-none select-none items-center',
        className
      )}
      {...props}
    />
  </Tailwind>
);

export type SliderTrackProps = React.ComponentProps<typeof RadixSlider.Track>;
export const Track = ({className, ...props}: SliderTrackProps) => (
  <RadixSlider.Track
    className={twMerge(
      'relative h-4 w-full grow rounded-[4px] bg-moon-350',
      className
    )}
    {...props}
  />
);

export type SliderRangeProps = React.ComponentProps<typeof RadixSlider.Range>;
export const Range = ({className, ...props}: SliderRangeProps) => (
  <RadixSlider.Range
    className={twMerge('absolute h-full rounded-[4px] bg-moon-350', className)}
    {...props}
  />
);

type SliderThumbProps = React.ComponentProps<typeof RadixSlider.Thumb>;
export const Thumb = ({className, ...props}: SliderThumbProps) => (
  <RadixSlider.Thumb
    className={twMerge(
      'block h-[22px] w-[22px] rounded-full border-[1px] border-solid border-moon-350 bg-white focus:outline focus:outline-[2px] focus:outline-teal-500 ',
      className
    )}
    {...props}
  />
);

type DisplayProps = {
  className?: string;
  isDirty?: boolean;
  isDisabled?: boolean;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  value: number | undefined;
};

export const Display = React.forwardRef(
  (p: DisplayProps, ref: React.Ref<HTMLInputElement>) => {
    const {
      className,
      isDirty = true,
      isDisabled = false,
      max,
      min,
      step,
      onChange,
      value,
      ...props
    } = p;
    return (
      <input
        className={twMerge(
          'ml-8  h-[40px] w-[56px] rounded border-[1px] border-solid border-moon-250 text-center focus:outline focus:outline-[2px] focus:outline-teal-500',
          isDirty ? 'text-moon-800' : 'text-moon-250',
          className
        )}
        disabled={isDisabled}
        max={max}
        min={min}
        step={step}
        onChange={e => onChange(Number(e.target.value))}
        ref={ref}
        type="number"
        value={value}
        {...props}
      />
    );
  }
);
