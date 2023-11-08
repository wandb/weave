import * as RadioGroup from '@radix-ui/react-radio-group';
import * as React from 'react';
import {twMerge} from 'tailwind-merge';

export const Root = ({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroup.Root>) => (
  <RadioGroup.Root className={twMerge('', className)} {...props} />
);

export const Item = ({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroup.Item>) => (
  <RadioGroup.Item
    className={twMerge(
      'flex h-[15px] w-[15px] items-center justify-center rounded-full border-[1px] border-solid border-moon-500 data-[state=checked]:border-moon-800',
      'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
      className
    )}
    {...props}
  />
);

export const Indicator = ({
  className,
  ...props
}: React.ComponentProps<typeof RadioGroup.Indicator>) => (
  <RadioGroup.Indicator
    className={twMerge('h-[9px] w-[9px] rounded-full bg-teal-500', className)}
    {...props}
  />
);

export const Radio = {
  Root,
  Item,
  Indicator,
};
