import * as RadixCheckbox from '@radix-ui/react-checkbox';
import classNames from 'classnames';
import React from 'react';

import {Tailwind} from '../Tailwind';

export type CheckboxState = RadixCheckbox.CheckedState;

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
};

/**
 * Our Checkbox component wraps {@link https://www.radix-ui.com/docs/primitives/components/checkbox
 * Radix Checkbox} and uses the same API except it's a strictly controlled component. This means
 * the `defaultChecked` is omitted and the `checked` prop is required.
 */

export const Checkbox = ({checked, className, ...props}: CheckboxProps) => {
  return (
    <Tailwind style={{display: 'flex', alignItems: 'center'}}>
      <RadixCheckbox.Root
        className={classNames(
          'night-aware',
          'inline-flex items-center justify-center',
          'h-18 w-18',
          'rounded border-[1.5px]  dark:border-moon-250',
          'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
          checked ? 'border-moon-800' : 'border-moon-500',
          {className}
        )}
        checked={checked}
        {...props}>
        <RadixCheckbox.Indicator
          className={classNames(
            'relative h-10 w-10 rounded-[1.5px]',
            'radix-state-checked:bg-teal-500 radix-state-indeterminate:bg-transparent radix-state-unchecked:bg-transparent',
            {
              // Indeterminate state styles
              "after:absolute after:top-4 after:block after:w-10 after:rounded-[1px] after:border-t-2 after:border-moon-800 after:content-[''] dark:after:border-moon-250":
                checked === 'indeterminate',
            }
          )}
        />
      </RadixCheckbox.Root>
    </Tailwind>
  );
};
