import * as RadixDialog from '@radix-ui/react-dialog';
import classNames from 'classnames';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Tailwind} from '../Tailwind';

/**
 * Our Dialog wraps {@link https://www.radix-ui.com/primitives/docs/components/dialog
 * Radix Dialog}.
 */
export const Root = (props: RadixDialog.DialogProps) => {
  return <RadixDialog.Root {...props} />;
};

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#trigger
 */
export const Trigger = (props: RadixDialog.DialogTriggerProps) => (
  <RadixDialog.Trigger asChild {...props} />
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#portal
 */
export const Portal = RadixDialog.Portal;

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#overlay
 */
const overlayClassName = classNames(
  'bg-oblivion/[0.24]',
  'fixed bottom-0 left-0 right-0 top-0',
  'grid place-items-center overflow-y-auto'
  // TODO - handle dark mode and add in 'night-aware'
);
export const Overlay = React.forwardRef(
  ({className, children, ...props}: RadixDialog.DialogOverlayProps, ref) => (
    <Tailwind>
      <RadixDialog.Content
        className={twMerge(overlayClassName, className)}
        {...props}>
        {children}
      </RadixDialog.Content>
    </Tailwind>
  )
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#content
 */
const contentClassName = classNames(
  'night-aware',
  'rounded border border-moon-250 bg-white py-6 shadow-md',
  'dark:border-moon-750 dark:bg-moon-900 dark:text-moon-200',
  'absolute left-[25%] top-[25%] '
);
export const Content = React.forwardRef(
  ({className, children, ...props}: RadixDialog.DialogContentProps, ref) => (
    <Tailwind>
      <RadixDialog.Content
        className={twMerge(contentClassName, className)}
        {...props}>
        {children}
      </RadixDialog.Content>
    </Tailwind>
  )
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#close
 */
export const Close = ({className, ...props}: RadixDialog.DialogCloseProps) => (
  <RadixDialog.Close className={twMerge(className)} {...props} />
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#title
 */
export const Title = (props: RadixDialog.DialogTitleProps) => (
  <RadixDialog.Title {...props} />
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#description
 */
export const Description = (props: RadixDialog.DialogDescriptionProps) => (
  <RadixDialog.Description {...props} />
);
