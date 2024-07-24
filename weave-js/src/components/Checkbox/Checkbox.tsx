import * as RadixCheckbox from '@radix-ui/react-checkbox';
import classNames from 'classnames';
import React from 'react';

import {Tailwind} from '../Tailwind';

export type CheckboxState = RadixCheckbox.CheckedState;
export type CheckboxSize = 'small' | 'medium';

/**
 * - {@link RadixCheckbox.CheckboxProps}
 * - https://www.radix-ui.com/docs/primitives/components/checkbox#root
 * All this does is make checked required and omit defaultChecked.
 */
export type CheckboxProps = Omit<
  RadixCheckbox.CheckboxProps,
  'defaultChecked' | 'checked'
> & {
  // "true | false | 'indeterminate'" is the type of RadixCheckbox.CheckedState
  checked: CheckboxState;
  size?: CheckboxSize;
};

/**
 * Our Checkbox component wraps {@link https://www.radix-ui.com/docs/primitives/components/checkbox
 * Radix Checkbox} and uses the same API except it's a strictly controlled component. This means
 * the `defaultChecked` is omitted and the `checked` prop is required.
 */

export const Checkbox = ({
  checked,
  className,
  size = 'medium',
  ...props
}: CheckboxProps) => {
  const isSmall = size === 'small';
  const isMedium = size === 'medium';
  const isIndeterminate = checked === 'indeterminate';

  return (
    <Tailwind style={{display: 'flex', alignItems: 'center'}}>
      <RadixCheckbox.Root
        className={classNames(
          'night-aware',
          'inline-flex items-center justify-center',
          'rounded border-[1.5px]  dark:border-moon-250',
          'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
          checked ? 'border-moon-800' : 'border-moon-500',
          props.disabled && 'opacity-30',
          {
            'h-14 w-14': isSmall,
            'h-18 w-18': isMedium,
          },
          {className}
        )}
        checked={checked}
        {...props}>
        <RadixCheckbox.Indicator
          className={classNames(
            'relative rounded-[1.5px]',
            'radix-state-checked:bg-teal-500 radix-state-indeterminate:bg-transparent radix-state-unchecked:bg-transparent',
            {
              'h-8 w-8': isSmall,
              'h-10 w-10': isMedium,
            },
            // Indeterminate state styles
            {
              "after:absolute after:block after:rounded-[1px] after:border-t-2 after:border-moon-800 after:content-[''] dark:after:border-moon-250":
                isIndeterminate,
              'after:top-3 after:w-8': isIndeterminate && isSmall,
              'after:top-4 after:w-10': isIndeterminate && isMedium,
            }
          )}
        />
      </RadixCheckbox.Root>
    </Tailwind>
  );
};
