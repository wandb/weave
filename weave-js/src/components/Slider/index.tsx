import * as RadixSlider from '@radix-ui/react-slider';
import React from 'react';
import {Tailwind} from '../Tailwind';

type SliderRootProps = React.ComponentProps<typeof RadixSlider.Root>;
const Root = (props: SliderRootProps) => (
  <Tailwind>
    <RadixSlider.Root className={''} {...props} />
  </Tailwind>
);

type SliderTrackProps = React.ComponentProps<typeof RadixSlider.Track>;
const Track = (props: SliderTrackProps) => (
  <RadixSlider.Track className="" {...props} />
);

type SliderRangeProps = React.ComponentProps<typeof RadixSlider.Range>;
const Range = (props: SliderRangeProps) => (
  <RadixSlider.Range className="" {...props} />
);

type SliderThumbProps = React.ComponentProps<typeof RadixSlider.Thumb>;
const Thumb = (props: SliderThumbProps) => (
  <RadixSlider.Thumb className="" {...props} />
);

const Slider = {
  Range,
  Root,
  Track,
  Thumb,
};

export default Slider;
