import classNames from 'classnames';
import React, {FC, ReactElement, useMemo, useRef} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {
  TruncateByCharsProps,
  TruncateByCharsWithTooltip,
} from '../TruncateByCharsWithTooltip';
import {RemoveAction} from './RemoveAction';
import {
  getRandomTagColor,
  getTagColorByString,
  getTagColorClass,
  getTagHoverClass,
  TAG_DEFAULT_MAX_CHARS,
  TagColorName,
} from './utils';

export const DEFAULT_TAG_ICON = 'tag';

/**
 * A Tag not given a specific color would have its color change every render cycle. This calculates a default color as a stable value, and only adds it to the class list when color isn't defined
 */
export function useTagClasses({
  color,
  isInteractive,
  label,
}: {
  color?: TagColorName;
  isInteractive?: boolean;
  label?: string;
}) {
  const randomColor = useRef(color || label ? undefined : getRandomTagColor());
  const labelHashColor = useMemo(
    () => (!color && label ? getTagColorByString(label) : undefined),
    [label, color]
  );
  const tagColor = color ?? labelHashColor ?? randomColor.current;

  return useMemo(
    () =>
      classNames(
        'night-aware',
        'min-h-22 flex max-h-22 w-fit items-center rounded-[3px] text-[14px]',
        getTagColorClass(tagColor),
        isInteractive ? getTagHoverClass(tagColor) : ''
      ),
    [isInteractive, tagColor]
  );
}

export type TagProps = TruncateByCharsProps & {
  label: string;
  color?: TagColorName;
  showIcon?: boolean;
  iconName?: IconName;
  endIconName?: IconName;
  isInteractive?: boolean;
};

export const Tag: FC<TagProps> = ({
  label,
  color,
  showIcon = false,
  iconName,
  endIconName,
  maxChars = TAG_DEFAULT_MAX_CHARS,
  truncatedPart,
  Wrapper = Tailwind,
  isInteractive = false,
}) => {
  const classes = useTagClasses({color, isInteractive, label});
  const truncationProps = {text: label, maxChars, truncatedPart, Wrapper};
  return (
    <TruncateByCharsWithTooltip {...truncationProps}>
      {({truncatedText}) => (
        <div className={twMerge(classes, showIcon ? 'pl-4 pr-6' : 'px-6')}>
          {showIcon && (
            <Icon
              role="presentation"
              className="mr-4 h-14 w-14"
              name={iconName ?? DEFAULT_TAG_ICON}
            />
          )}
          <span>{truncatedText}</span>
          {endIconName && (
            <Icon
              role="presentation"
              className="ml-4 h-14 w-14"
              name={endIconName}
            />
          )}
        </div>
      )}
    </TruncateByCharsWithTooltip>
  );
};

export type RemovableTagProps = TruncateByCharsProps &
  Omit<TagProps, 'isInteractive'> & {
    removeAction: ReactElement<typeof RemoveAction>;
  };
export const RemovableTag: FC<RemovableTagProps> = ({
  label,
  removeAction,
  color,
  showIcon = false,
  iconName,
  maxChars = TAG_DEFAULT_MAX_CHARS,
  truncatedPart,
  Wrapper = Tailwind,
}) => {
  const classes = useTagClasses({color, isInteractive: true, label});
  const truncationProps = {text: label, maxChars, truncatedPart, Wrapper: null};
  if (Wrapper === null) {
    Wrapper = React.Fragment;
  }
  return (
    <Wrapper>
      <div className={twMerge(classes, showIcon ? 'px-4' : 'pl-6 pr-4')}>
        {showIcon && (
          <Icon
            role="presentation"
            className="mr-4 h-14 w-14"
            name={iconName ?? DEFAULT_TAG_ICON}
          />
        )}
        <TruncateByCharsWithTooltip {...truncationProps}>
          {({truncatedText}) => <span>{truncatedText}</span>}
        </TruncateByCharsWithTooltip>
        {removeAction}
      </div>
    </Wrapper>
  );
};
