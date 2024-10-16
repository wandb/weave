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
  'night-aware',
  'bg-oblivion/[0.24] dark:bg-oblivion/[0.48]',
  'fixed bottom-0 left-0 right-0 top-0',
  'grid place-items-center overflow-y-auto',
  'z-[1001]'
);
export const Overlay = React.forwardRef(
  ({className, children, ...props}: RadixDialog.DialogOverlayProps, ref) => (
    <Tailwind>
      <RadixDialog.Overlay
        className={twMerge(overlayClassName, className)}
        {...props}>
        {children}
      </RadixDialog.Overlay>
    </Tailwind>
  )
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#content
 */
const contentClassName = classNames(
  'night-aware',
  'fixed left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%]', // centers modal on screen
  'rounded border py-24 px-32',
  'shadow-lg shadow-oblivion/[0.16] dark:shadow-oblivion/[0.48]',
  'border-moon-250 bg-white text-moon-850',
  'dark:border-moon-750 dark:bg-moon-900 dark:text-moon-150',
  'z-[1001]'
);
export const Content = React.forwardRef<
  HTMLDivElement,
  RadixDialog.DialogContentProps
>(({className, children, ...props}, ref) => (
  <Tailwind>
    <RadixDialog.Content
      ref={ref}
      className={twMerge(contentClassName, className)}
      {...props}>
      {children}
    </RadixDialog.Content>
  </Tailwind>
));

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#close
 */
export const Close = ({className, ...props}: RadixDialog.DialogCloseProps) => (
  <RadixDialog.Close className={twMerge(className)} {...props} />
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#title
 */
export const Title = ({className, ...props}: RadixDialog.DialogTitleProps) => (
  <RadixDialog.Title
    className={twMerge('leading-40 text-2xl font-semibold', className)}
    {...props}
  />
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dialog#description
 */
export const Description = ({
  className,
  ...props
}: RadixDialog.DialogDescriptionProps) => (
  <RadixDialog.Description className={twMerge('mt-4', className)} {...props} />
);
