/**
 * This button component is built to July 2023 specifications from the design team
 * This version can be used in Tailwind contexts.
 * https://www.figma.com/file/01KWBdMZg5QM9SRS1pQq0z/Design-System----Robot-Styles?type=design&node-id=5956-31813&mode=design&t=Gm4WWGWwgjdfUUTe-0
 */

import {TooltipContentProps} from '@radix-ui/react-tooltip';
import classNames from 'classnames';
import React, {ReactElement, useState} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import * as Tooltip from '../RadixTooltip';
import {Tailwind} from '../Tailwind';
import {ButtonSize, ButtonVariant} from './types';

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  /**
   * Shorthand alias for `startIcon` since most button icons are startIcons.
   * If both props are provided, `startIcon` value will be used out of the two.
   */
  icon?: IconName;
  /**
   * Icon displayed before the children
   */
  startIcon?: IconName;
  /**
   * Icon displayed after the children
   */
  endIcon?: IconName;
  size?: ButtonSize;
  variant?: ButtonVariant;
  children?: ReactElement | string;
  active?: boolean;
  tooltip?: string;
  tooltipProps?: TooltipContentProps;
  twWrapperStyles?: React.CSSProperties;
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      size = 'medium',
      variant = 'primary',
      icon,
      startIcon = icon,
      endIcon,
      active,
      children,
      className = '',
      tooltip,
      tooltipProps,
      twWrapperStyles = {},
      ...htmlAttributes
    },
    ref
  ) => {
    const hasIcon = startIcon || endIcon;
    if (!children && !hasIcon) {
      console.error('Button: requires either children or an icon.');
    }

    const isSmall = size === 'small';
    const isMedium = size === 'medium';
    const isLarge = size === 'large';
    const isPrimary = variant === 'primary';
    const isSecondary = variant === 'secondary';
    const isGhost = variant === 'ghost';
    const isQuiet = variant === 'quiet';
    const isDestructive = variant === 'destructive';

    const hasBothIcons = startIcon && endIcon;
    const hasOnlyOneIcon = hasIcon && !hasBothIcons;
    const isIconOnly = hasOnlyOneIcon && !children;

    /**
     * The Tailwind wrapper is a div, which is a block-element. However, a normal button
     * wouldn't be wrapped and would be inline-block by default. These styles are a
     * necessary workaround to ensure Button is styled correctly despite the wrapper.
     */
    const wrapperStyles = {
      display: 'inline-flex',
      width: className.includes('w-full') ? '100%' : undefined,
      ...twWrapperStyles,
    };

    const button = (
      <button
        ref={ref}
        type="button"
        className={twMerge(
          classNames(
            'night-aware',
            "inline-flex items-center justify-center whitespace-nowrap rounded border-none font-['Source_Sans_Pro'] font-semibold",
            'disabled:pointer-events-none disabled:opacity-35',
            'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
            {
              // small
              'gap-6 px-6 py-3 text-sm leading-[18px]': isSmall,
              '[&_svg]:h-16 [&_svg]:w-16': isSmall,
              'h-24 w-24 p-0': isSmall && isIconOnly,

              // medium
              'gap-10 px-10 py-4 text-base': isMedium,
              '[&_svg]:h-18 [&_svg]:w-18': isMedium,
              'h-32 w-32 p-0': isMedium && isIconOnly,

              // large
              'gap-8 px-12 py-8 text-base': isLarge,
              'h-40 w-40 p-0': isLarge && isIconOnly,

              // primary
              'bg-teal-500 text-white hover:bg-teal-450': isPrimary,
              'bg-teal-450': isPrimary && active,

              // secondary & ghost
              'bg-oblivion/[0.05] dark:bg-moonbeam/[0.05]': isSecondary,
              'text-moon-800 dark:text-moon-200': isSecondary || isGhost,
              'hover:bg-teal-300/[0.48] hover:text-teal-600 dark:hover:bg-teal-700/[0.48] dark:hover:text-teal-400':
                isSecondary || isGhost,
              'bg-teal-300/[0.48] text-teal-600 dark:bg-teal-700/[0.48] dark:text-teal-400':
                (isSecondary || isGhost) && active,

              // quiet
              'text-moon-500': isQuiet,
              'bg-oblivion/[0.05] text-moon-800 dark:bg-moonbeam/[0.05] dark:text-moon-200':
                isQuiet && active,
              'hover:text-moon-800 dark:hover:text-moon-200': isQuiet,
              'hover:bg-oblivion/[0.05] dark:hover:bg-moonbeam/[0.05]': isQuiet,

              // destructive
              'bg-red-500 text-white hover:bg-red-450': isDestructive,
              'bg-red-450': isDestructive && active,
            },
            className
          )
        )}
        {...htmlAttributes}>
        {startIcon ? <Icon name={startIcon} /> : null}
        {children}
        {endIcon ? <Icon name={endIcon} /> : null}
      </button>
    );

    const [isTooltipOpen, setIsTooltipOpen] = useState(false);
    if (tooltip) {
      return (
        <Tailwind style={wrapperStyles}>
          <Tooltip.Provider>
            <Tooltip.Root open={isTooltipOpen} onOpenChange={setIsTooltipOpen}>
              <Tooltip.Trigger asChild>
                {/* span is needed so tooltip works on disabled buttons */}
                <span>{button}</span>
              </Tooltip.Trigger>
              <Tooltip.Portal>
                <Tooltip.Content {...tooltipProps}>{tooltip}</Tooltip.Content>
              </Tooltip.Portal>
            </Tooltip.Root>
          </Tooltip.Provider>
        </Tailwind>
      );
    }

    return <Tailwind style={wrapperStyles}>{button}</Tailwind>;
  }
);
