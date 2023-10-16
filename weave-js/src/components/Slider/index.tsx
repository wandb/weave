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
      'block h-[22px] w-[22px] rounded-full border-[1px] border-solid border-moon-350 bg-white',
      className
    )}
    {...props}
  />
);

export const Slider = {
  Root,
  Track,
  Range,
  Thumb,
};
