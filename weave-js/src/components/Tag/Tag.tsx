import classNames from 'classnames';
import React, {
  FC,
  ReactElement,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {twMerge} from 'tailwind-merge';

import {Icon, IconName} from '../Icon';
import {Tailwind} from '../Tailwind';
import {RemoveAction} from './RemoveAction';
import {TagTooltip} from './TagTooltip';
import {
  getRandomTagColor,
  getTagColorByString,
  getTagColorClass,
  getTagHoverClass,
  isTagLabelTruncated,
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

export type TagProps = {
  label: string;
  color?: TagColorName;
  showIcon?: boolean;
  iconName?: IconName;
  endIconName?: IconName;
  // Wrapping the Tag in Tailwind can be a problem if the Tailwind wrapper is supplied higher up
  // and there is a need to position the Tag as a direct child for something like flexbox
  Wrapper?: React.ComponentType<any> | null;
  isInteractive?: boolean;
};

export const Tag: FC<TagProps> = ({
  label,
  color,
  showIcon = false,
  iconName,
  endIconName,
  Wrapper = Tailwind,
  isInteractive = false,
}) => {
  const classes = useTagClasses({color, isInteractive, label});

  const nakedTag = (
    <div className={twMerge(classes, showIcon ? 'pl-4 pr-6' : 'px-6')}>
      {showIcon && (
        <Icon
          role="presentation"
          className="mr-4 h-14 w-14"
          name={iconName ?? DEFAULT_TAG_ICON}
        />
      )}
      <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
        {label}
      </span>
      {endIconName && <Icon className="ml-4 h-14 w-14" name={endIconName} />}
    </div>
  );
  if (Wrapper) {
    return <Wrapper>{nakedTag}</Wrapper>;
  }

  return nakedTag;
};

export type RemovableTagProps = Omit<TagProps, 'isInteractive'> & {
  removeAction: ReactElement<typeof RemoveAction>;
};
export const RemovableTag: FC<RemovableTagProps> = ({
  label,
  removeAction,
  color,
  showIcon = false,
  iconName,
  Wrapper = Tailwind,
}) => {
  const labelRef = useRef<HTMLParagraphElement>(null);
  const [isTruncated, setIsTruncated] = useState(false);

  useEffect(() => {
    if (labelRef.current) {
      setIsTruncated(isTagLabelTruncated(labelRef));
    }
  }, [label]);

  const classes = useTagClasses({color, isInteractive: true, label});

  const nakedTag = (
    <TagTooltip value={label} disabled={!isTruncated}>
      <div className={twMerge(classes, showIcon ? 'px-4' : 'pl-6 pr-4')}>
        {showIcon && (
          <Icon
            role="presentation"
            className="mr-4 h-14 w-14"
            name={iconName ?? DEFAULT_TAG_ICON}
          />
        )}
        <p
          className={twMerge(
            'max-w-[172px]', // 172px =  MAX_TAG_LABEL_WIDTH_PX + 14 (account for remove action button)
            'overflow-hidden text-ellipsis whitespace-nowrap'
          )}
          ref={labelRef}>
          {label}
        </p>
        {removeAction}
      </div>
    </TagTooltip>
  );
  if (Wrapper) {
    return <Wrapper>{nakedTag}</Wrapper>;
  }
  return nakedTag;
};
