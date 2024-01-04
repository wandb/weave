import * as RadixTabs from '@radix-ui/react-tabs';
import classNames from 'classnames';
import React from 'react';
import {Link, LinkProps} from 'react-router-dom';

import {Tailwind} from '../Tailwind';

/**
 * - {@link RadixTabs.TabsProps}
 * - https://www.radix-ui.com/docs/primitives/components/tabs#root
 */
export type TabsProps = Omit<RadixTabs.TabsProps, 'defaultValue'> & {
  value: string;
};

/**
 * Our Tabs component wraps {@link https://www.radix-ui.com/docs/primitives/components/tabs
 * Radix Tabs} and uses the same API except it's a strictly controlled component. This means
 * the `defaultValue` prop is omitted and the `value` prop is required.
 */
export const Root = (props: TabsProps) => {
  return (
    <Tailwind>
      <RadixTabs.Root {...props} />
    </Tailwind>
  );
};

/**
 * - https://www.radix-ui.com/docs/primitives/components/tabs#list
 */
export const List = ({className, ...props}: RadixTabs.TabsListProps) => (
  <RadixTabs.List
    className={classNames(
      'night-aware',
      'flex gap-32 border-b border-moon-250',
      'dark:border-moon-800',
      className
    )}
    {...props}
  />
);

/**
 * {@link https://www.radix-ui.com/docs/primitives/components/tabs#trigger}
 */
export const Trigger = ({className, ...props}: RadixTabs.TabsTriggerProps) => (
  <RadixTabs.Trigger
    className={classNames(
      'flex items-center gap-6',
      '-mb-px border-b-2 pb-4 leading-8',
      'font-semibold leading-8 text-moon-500 dark:text-moon-600',
      'focus:outline-none focus-visible:ring',
      'hover:text-moon-800 dark:hover:text-moon-100',
      'border-transparent radix-state-active:border-teal-500',
      'radix-state-active:text-moon-800 dark:radix-state-active:text-moon-100',
      'disabled:pointer-events-none disabled:text-moon-350 dark:disabled:text-moon-650',
      'transition duration-100',
      // `[&_svg]` selects svg elements inside this element (i.e. icons in icon tabs)
      // https://tailwindcss.com/docs/hover-focus-and-other-states#using-arbitrary-variants
      '[&_svg]:-ml-2 [&_svg]:h-18 [&_svg]:w-18',
      className
    )}
    {...props}
  />
);

/**
 * Use this component instead of `Trigger` for tabs with URL navigation.
 *
 * Accepts the combined props of
 * {@link https://www.radix-ui.com/docs/primitives/components/tabs#trigger Tabs Trigger}
 * and {@link https://reactrouter.com/en/main/components/link React Router Link}.
 * If no `to` prop is specified, link destination defaults to the Trigger `value`.
 */
export const LinkedTrigger = ({
  value,
  to = value,
  children,
  ...props
}: RadixTabs.TabsTriggerProps & Partial<LinkProps>) => (
  <Trigger value={value} {...props} asChild>
    <Link to={to}>{children}</Link>
  </Trigger>
);

/**
 * - https://www.radix-ui.com/docs/primitives/components/tabs#content
 */
export const Content = RadixTabs.Content;
