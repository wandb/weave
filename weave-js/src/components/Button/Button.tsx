/**
 * This button component is built to July 2023 specifications from the design team
 * This version can be used in Tailwind contexts.
 * https://www.figma.com/file/01KWBdMZg5QM9SRS1pQq0z/Design-System----Robot-Styles?type=design&node-id=5956-31813&mode=design&t=Gm4WWGWwgjdfUUTe-0
 */

import {type TooltipContentProps} from '@radix-ui/react-tooltip';
import classNames from 'classnames';
import React, {
  CSSProperties,
  forwardRef,
  type ReactElement,
  useState,
} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, type IconName} from '../Icon';
import * as Tooltip from '../RadixTooltip';
import {Tailwind} from '../Tailwind';
import type {ButtonSize, ButtonVariant} from './types';

type IconButtonProps = {
  icon?: IconName;
  children?: never;
  startIcon?: never;
  endIcon?: never;
  tooltip: string;
};

type LabelButtonProps = {
  icon?: never;
  children: ReactElement | string;
  startIcon?: IconName;
  endIcon?: IconName;
  tooltip?: string;
};

export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  size?: ButtonSize;
  variant?: ButtonVariant;
  children?: ReactElement | string;
  active?: boolean;
  tooltip?: string;
  tooltipProps?: TooltipContentProps;
  twWrapperStyles?: React.CSSProperties;
} & (IconButtonProps | LabelButtonProps);

const sizeMap = {
  small:
    'gap-6 px-6 py-3 text-sm leading-[18px] [&_svg]:h-16 [&_svg]:w-16 h-24 w-24 p-0',
  medium: 'gap-10 px-10 py-4 text-base [&_svg]:h-18 [&_svg]:w-18 h-32 w-32 p-0',
  large: 'gap-8 px-12 py-8 text-base h-40 w-40 p-0',
};

const variantMap = {
  primary: 'bg-teal-500 text-white hover:bg-teal-450',
  secondary:
    'bg-oblivion/[0.05] dark:bg-moonbeam/[0.05] text-moon-800 dark:text-moon-200 hover:bg-teal-300/[0.48] hover:text-teal-600 dark:hover:bg-teal-700/[0.48] dark:hover:text-teal-400',
  ghost:
    'bg-oblivion/[0.05] dark:bg-moonbeam/[0.05] text-moon-800 dark:text-moon-200 hover:bg-teal-300/[0.48] hover:text-teal-600 dark:hover:bg-teal-700/[0.48] dark:hover:text-teal-400',
  quiet:
    'text-moon-500 hover:text-moon-800 dark:hover:text-moon-200 hover:bg-oblivion/[0.05] dark:hover:bg-moonbeam/[0.05]',
  destructive: 'bg-red-500 text-white hover:bg-red-450',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      size = 'medium',
      variant = 'primary',
      icon,
      startIcon,
      endIcon,
      active,
      children,
      className = '',
      tooltip,
      tooltipProps,
      twWrapperStyles,
      ...htmlAttributes
    },
    ref
  ) => {
    /**
     * The Tailwind wrapper is a div, which is a block-element. However, a normal button
     * wouldn't be wrapped and would be inline-block by default. These styles are a
     * necessary workaround to ensure Button is styled correctly despite the wrapper.
     */
    const wrapperStyles: CSSProperties = {
      display: 'inline-flex',
      width: className.includes('w-full') ? '100%' : undefined,
      ...twWrapperStyles,
    };

    /**
     * Runtime validation of props' type constraints
     */
    const ButtonInner = () => {
      if (icon) {
        if (children || startIcon || endIcon) {
          console.warn(
            'Button: `startIcon`, `endIcon`, and `children` are ignored when using `icon`.'
          );
        }
        return <Icon name={icon} role="presentation" />;
      }

      if (!children) {
        console.error('Button: `children` is required when not using `icon`.');
        return null;
      }

      return (
        <>
          {startIcon ? <Icon name={startIcon} role="presentation" /> : null}
          {children}
          {endIcon ? <Icon name={endIcon} role="presentation" /> : null}
        </>
      );
    };

    const ButtonInternal = () => (
      <button
        ref={ref}
        {...htmlAttributes}
        type="button"
        aria-disabled={htmlAttributes.disabled}
        aria-label={htmlAttributes['aria-label'] || tooltip}
        className={twMerge(
          classNames(
            'night-aware',
            "inline-flex items-center justify-center whitespace-nowrap rounded border-none font-['Source_Sans_Pro'] font-semibold",
            'disabled:pointer-events-none disabled:opacity-35',
            'focus-visible:outline focus-visible:outline-[2px] focus-visible:outline-teal-500',
            sizeMap[size] + (icon && !children ? ' h-24 w-24 p-0' : ''),
            variantMap[variant] + (active ? ' bg-teal-450' : ''),
            className
          )
        )}>
        <ButtonInner />
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
                <span>
                  <ButtonInternal />
                </span>
              </Tooltip.Trigger>
              <Tooltip.Portal>
                <Tooltip.Content {...tooltipProps}>{tooltip}</Tooltip.Content>
              </Tooltip.Portal>
            </Tooltip.Root>
          </Tooltip.Provider>
        </Tailwind>
      );
    }

    return (
      <Tailwind style={wrapperStyles}>
        <ButtonInternal />
      </Tailwind>
    );
  }
);
