import * as RadixTooltip from '@radix-ui/react-tooltip';
import classNames from 'classnames';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Tailwind} from '../Tailwind';

/**
 * {@link https://www.radix-ui.com/docs/primitives/components/tooltip#trigger}
 */
export const Provider = (props: RadixTooltip.TooltipProviderProps) => (
  <RadixTooltip.Provider
    delayDuration={250}
    skipDelayDuration={100}
    {...props}
  />
);

/**
 * - {@link RadixTooltip.TooltipProps}
 * - https://www.radix-ui.com/docs/primitives/components/tooltip#root
 */
export type TooltipProps = Omit<RadixTooltip.TooltipProps, 'defaultOpen'> & {
  open: boolean;
};

/**
 * Our Tooltip wraps {@link https://www.radix-ui.com/docs/primitives/components/tooltip
 * Radix Tooltip} but is a strictly controlled component. This means the `defaultOpen` prop
 * is omitted and the `open` prop is required.
 */
export const Root = (props: TooltipProps) => {
  return <RadixTooltip.Root {...props} />;
};

/**
 * Note: if your trigger is a button, you should use `asChild` prop
 * https://www.radix-ui.com/docs/primitives/components/tooltip#trigger
 */
export const Trigger = ({
  className,
  ...props
}: RadixTooltip.TooltipTriggerProps) => (
  <RadixTooltip.Trigger
    className={twMerge(classNames('cursor-default', className))}
    {...props}
  />
);

/**
 * https://www.radix-ui.com/docs/primitives/components/tooltip#portal
 */
export const Portal = RadixTooltip.Portal;

/**
 * https://www.radix-ui.com/docs/primitives/components/tooltip#content
 */
export const Content = React.forwardRef(
  ({className, children, ...props}: RadixTooltip.TooltipContentProps, ref) => (
    <Tailwind>
      <RadixTooltip.Content
        className={twMerge(
          classNames(
            'rounded bg-white text-sm text-moon-800 shadow-md',
            className
          )
        )}
        sideOffset={5}
        {...props}>
        {children}
      </RadixTooltip.Content>
    </Tailwind>
  )
);
