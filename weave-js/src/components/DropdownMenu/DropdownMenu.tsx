import * as RadixDropdownMenu from '@radix-ui/react-dropdown-menu';
import classNames from 'classnames';
import React from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon} from '../Icon';
import {Tailwind} from '../Tailwind';

/**
 * - {@link RadixDropdownMenu.DropdownMenuProps}
 * - https://www.radix-ui.com/docs/primitives/components/dropdown-menu#root
 */
export type DropdownMenuProps = Omit<
  RadixDropdownMenu.DropdownMenuProps,
  'defaultOpen'
> & {
  open: boolean;
};

/**
 * Our DropdownMenu wraps {@link https://www.radix-ui.com/docs/primitives/components/dropdown-menu
 * Radix DropdownMenu} but is a strictly controlled component. This means the `defaultOpen` prop
 * is omitted and the `open` prop is required.
 */
export const Root = (props: DropdownMenuProps) => {
  return <RadixDropdownMenu.Root {...props} />;
};

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#trigger
 */
export const Trigger = (props: RadixDropdownMenu.DropdownMenuTriggerProps) => (
  <RadixDropdownMenu.Trigger asChild {...props} />
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#portal
 */
export const Portal = RadixDropdownMenu.Portal;

/**
 * Styles for menu contents. Also used for submenu contents.
 */
const contentClassName = classNames(
  'night-aware',
  'rounded border border-moon-250 bg-white py-6 shadow-md',
  'dark:border-moon-750 dark:bg-moon-900 dark:text-moon-200'
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#content
 */
export const Content = React.forwardRef<
  HTMLDivElement,
  RadixDropdownMenu.DropdownMenuContentProps
>(({className, children, ...props}, ref) => (
  <Tailwind>
    <RadixDropdownMenu.Content
      ref={ref}
      className={twMerge(contentClassName, className)}
      sideOffset={5}
      {...props}>
      {children}
    </RadixDropdownMenu.Content>
  </Tailwind>
));

/**
 * https://www.radix-ui.com/primitives/docs/components/dropdown-menu#group
 */
export const Group = (props: RadixDropdownMenu.MenuGroupProps) => (
  <RadixDropdownMenu.Group {...props} />
);
/**
 * Styles for menu items. Also used for submenu triggers.
 */
const baseItemClassName = classNames(
  'flex cursor-pointer items-center gap-10 rounded',
  'mx-6 px-10 py-6',
  '[&_svg]:h-18 [&_svg]:w-18',
  'hover:bg-moon-100 hover:outline-none dark:hover:bg-moon-800',
  'radix-disabled:pointer-events-none radix-disabled:text-moon-350 dark:radix-disabled:text-moon-650'
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dropdown-menu#label
 */
export const Label = (props: RadixDropdownMenu.MenuLabelProps) => (
  <RadixDropdownMenu.Label {...props} />
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#item
 */
export const Item = ({
  className,
  ...props
}: RadixDropdownMenu.DropdownMenuItemProps) => (
  <RadixDropdownMenu.Item
    className={twMerge(baseItemClassName, className)}
    {...props}
  />
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#separator
 */
export const Separator = ({
  className,
  ...props
}: RadixDropdownMenu.DropdownMenuSeparatorProps) => (
  <RadixDropdownMenu.Separator
    className={twMerge(
      classNames('my-6 h-px bg-moon-250 dark:bg-moon-750', className)
    )}
    {...props}
  />
);

/**
 * - {@link RadixDropdownMenu.DropdownMenuSubProps}
 * - https://www.radix-ui.com/docs/primitives/components/dropdown-menu#sub
 */
export type DropdownMenuSubProps = Omit<
  RadixDropdownMenu.DropdownMenuSubProps,
  'defaultOpen'
> & {
  open: boolean;
};

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#sub
 */
export const Sub = (props: DropdownMenuSubProps) => (
  <RadixDropdownMenu.Sub {...props} />
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#subtrigger
 */
export const SubTrigger = ({
  className,
  ...props
}: RadixDropdownMenu.MenuSubTriggerProps) => (
  <RadixDropdownMenu.SubTrigger
    className={twMerge(
      baseItemClassName,
      'radix-state-open:bg-moon-100',
      'radix-state-open:outline-none',
      'dark:radix-state-open:bg-moon-800',
      className
    )}
    {...props}
  />
);
/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#subcontent
 */
export const SubContent = React.forwardRef<
  HTMLDivElement,
  RadixDropdownMenu.MenuSubTriggerProps
>(({children, className, ...props}, ref) => (
  <Tailwind>
    <RadixDropdownMenu.SubContent
      ref={ref}
      className={twMerge(contentClassName, className)}
      sideOffset={13}
      alignOffset={-7}
      {...props}>
      {children}
    </RadixDropdownMenu.SubContent>
  </Tailwind>
));

/**
 * - {@link RadixDropdownMenu.DropdownMenuRadioGroupProps}
 * - https://www.radix-ui.com/docs/primitives/components/dropdown-menu#radiogroup
 */
export type DropdownMenuRadioGroupProps =
  RadixDropdownMenu.DropdownMenuRadioGroupProps & {
    value: string;
  };

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#radiogroup
 */
export const RadioGroup = (props: DropdownMenuRadioGroupProps) => (
  <RadixDropdownMenu.RadioGroup {...props} />
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#radioitem
 */
export const RadioItem = ({
  className,
  children,
  ...props
}: RadixDropdownMenu.DropdownMenuRadioItemProps) => (
  <RadixDropdownMenu.RadioItem
    className={twMerge(baseItemClassName, className)}
    {...props}>
    {children}
  </RadixDropdownMenu.RadioItem>
);

/**
 * https://www.radix-ui.com/primitives/docs/components/dropdown-menu#checkboxitem
 */
export const CheckboxItem = ({
  className,
  children,
  ...props
}: RadixDropdownMenu.DropdownMenuCheckboxItemProps) => (
  <RadixDropdownMenu.CheckboxItem
    className={twMerge(baseItemClassName, className)}
    {...props}>
    {children}
  </RadixDropdownMenu.CheckboxItem>
);

/**
 * https://www.radix-ui.com/docs/primitives/components/dropdown-menu#itemindicator
 */
export const ItemIndicator = RadixDropdownMenu.ItemIndicator;

/**
 * Custom [ItemIndicator](https://www.radix-ui.com/docs/primitives/components/dropdown-menu#itemindicator)
 * to indicate the selected item in the style of radio buttons
 */
export const ItemIndicatorRadio = () => (
  <div className="ml-auto flex h-16 w-16 items-center justify-center rounded-full border border-solid border-moon-450">
    <ItemIndicator className="block h-10 w-10 rounded-full bg-teal-500" />
  </div>
);

/**
 * Custom [ItemIndicator](https://www.radix-ui.com/docs/primitives/components/dropdown-menu#itemindicator)
 * to indicate the selected item with a checkmark icon
 */
export const ItemIndicatorCheckmark = () => (
  <ItemIndicator>
    <Icon name="checkmark" />
  </ItemIndicator>
);
