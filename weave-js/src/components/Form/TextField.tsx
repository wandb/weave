/**
 * A form text input.
 *
 * Design:
 * https://www.figma.com/file/01KWBdMZg5QM9SRS1pQq0z/Design-System----Robot-Styles?type=design&node-id=92%3A1442&t=141heo3Rv8zF83xH-1
 */

import {Icon, IconName} from '@wandb/weave/components/Icon';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import classNames from 'classnames';
import React from 'react';

export const TextFieldSizes = {
  Medium: 'medium',
  Large: 'large',
} as const;
export type TextFieldSize =
  (typeof TextFieldSizes)[keyof typeof TextFieldSizes];

type TextFieldProps = {
  size?: TextFieldSize;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  onKeyDown?: (key: string) => void;
  onBlur?: (value: string) => void;
  autoFocus?: boolean;
  disabled?: boolean;
  icon?: IconName;
  ariaLabel?: string;
  errorState?: boolean;
  prefix?: string;
  extraActions?: React.ReactNode;
  maxLength?: number;
  type?: string;
  autoComplete?: string;
  dataTest?: string;
};

export const TextField = ({
  size,
  placeholder,
  value,
  onChange,
  onKeyDown,
  onBlur,
  autoFocus,
  disabled,
  icon,
  ariaLabel,
  errorState,
  prefix,
  extraActions,
  maxLength,
  type,
  autoComplete,
  dataTest,
}: TextFieldProps) => {
  const textFieldSize = size ?? 'medium';

  const handleChange = onChange
    ? (e: React.ChangeEvent<HTMLInputElement>) => {
        onChange(e.target.value);
      }
    : undefined;
  const handleKeyDown = onKeyDown
    ? (e: React.KeyboardEvent<HTMLInputElement>) => {
        onKeyDown(e.key);
      }
    : undefined;
  const handleBlur = onBlur
    ? (e: React.ChangeEvent<HTMLInputElement>) => {
        onBlur?.(e.target.value);
      }
    : undefined;

  return (
    <Tailwind style={{width: '100%'}}>
      <div
        className={classNames(
          'relative',
          textFieldSize === 'medium' ? 'h-32' : 'h-40'
        )}>
        <div
          className={classNames(
            'absolute bottom-0 top-0 flex w-full items-center rounded-sm',
            'outline outline-1 outline-moon-250',
            disabled
              ? 'opacity-50'
              : 'hover:outline hover:outline-2 hover:outline-teal-500/40 focus:outline-2',
            errorState
              ? 'outline outline-2 outline-red-450 hover:outline-red-450 focus:outline-red-450'
              : 'outline outline-1 outline-moon-250 hover:outline-teal-500/40 focus:outline-teal-500/40'
          )}>
          {prefix && <div className="text-gray-800 pl-8 pr-1">{prefix}</div>}
          <input
            className={classNames(
              'h-full w-full flex-1',
              'appearance-none border-none',
              'focus:outline-none',
              'placeholder-moon-500 dark:placeholder-moon-600',
              icon
                ? textFieldSize === 'medium'
                  ? 'pl-34'
                  : 'pl-36'
                : prefix
                ? null
                : 'pl-8'
            )}
            placeholder={placeholder}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            autoFocus={autoFocus}
            disabled={disabled}
            readOnly={!onChange} // It would be readonly regardless but this prevents a console warning
            aria-label={ariaLabel}
            maxLength={maxLength}
            type={type}
            autoComplete={autoComplete}
            data-test={dataTest}
          />
          {extraActions}
        </div>

        {icon && (
          <Icon
            name={icon}
            className={classNames(
              'absolute left-8',
              textFieldSize === 'medium'
                ? 'top-8 h-18 w-18'
                : 'top-10  h-20 w-20',
              value ? 'text-moon-800' : 'text-moon-500'
            )}
          />
        )}
      </div>
    </Tailwind>
  );
};
