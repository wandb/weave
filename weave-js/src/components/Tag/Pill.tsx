import React, {FC} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {
  TruncateByCharsProps,
  TruncateByCharsWithTooltip,
} from '../TruncateByCharsWithTooltip';
import {useTagClasses} from './Tag';
import {TAG_DEFAULT_MAX_CHARS, TagColorName} from './utils';

export type PillProps = TruncateByCharsProps & {
  label: string;
  icon?: IconName;
  color?: TagColorName;
  className?: string;
  isInteractive?: boolean;
};
export const Pill: FC<PillProps> = ({
  label,
  icon,
  color,
  className,
  isInteractive,
  maxChars = TAG_DEFAULT_MAX_CHARS,
  truncatedPart,
  Wrapper,
}) => {
  const classes = useTagClasses({color, isInteractive});
  const truncationProps = {text: label, maxChars, truncatedPart, Wrapper};
  return (
    <TruncateByCharsWithTooltip {...truncationProps}>
      {({truncatedText}) => (
        <div
          className={twMerge(
            classes,
            'rounded-2xl',
            icon ? 'pl-4 pr-7' : 'px-7',
            className
          )}>
          {icon && (
            <Icon role="presentation" className="mr-4 h-14 w-14" name={icon} />
          )}
          <span>{truncatedText}</span>
        </div>
      )}
    </TruncateByCharsWithTooltip>
  );
};

export type IconOnlyPillProps = {
  icon: IconName;
  color?: TagColorName;
  isInteractive?: boolean;
};
export const IconOnlyPill: FC<IconOnlyPillProps> = ({
  icon,
  color,
  isInteractive,
}) => {
  const classes = useTagClasses({color, isInteractive});
  return (
    <Tailwind>
      <div className={twMerge(classes, 'rounded-2xl', 'max-w-[22px]')}>
        <Icon role="presentation" className="m-4 h-14 w-14" name={icon} />
      </div>
    </Tailwind>
  );
};

export type ExpandingPillProps = {
  className?: string;
  color?: TagColorName;
  icon: IconName;
  label: string;
};
export const ExpandingPill = ({
  className,
  color,
  icon,
  label,
}: ExpandingPillProps) => {
  const classes = useTagClasses({color, isInteractive: true});
  return (
    <Tailwind>
      <div
        className={twMerge(
          classes,
          'rounded-2xl p-4',
          'max-w-[22px] hover:max-w-[25ch]',
          // note: transition delay + duration = 500ms, which matches our default tooltip delay
          // so that when pairing a pill with a tooltip, the tooltip doesn't lag and appear later
          'transition-[max-width] delay-200 duration-300',
          '[&:hover_span]:opacity-100 [&_span]:opacity-0',
          className
        )}>
        <Icon className="h-14 w-14 shrink-0" name={icon} role="presentation" />
        <span
          className={twMerge(
            'max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap px-4',
            'transition-opacity delay-200 duration-300'
          )}>
          {label}
        </span>
      </div>
    </Tailwind>
  );
};
