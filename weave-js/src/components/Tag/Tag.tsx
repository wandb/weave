import classNames from 'classnames';
import React, {FC, ReactElement} from 'react';

import {Icon} from '../Icon';
import {Tailwind} from '../Tailwind';
import {RemoveAction} from './RemoveAction';
import {getTagColor, TagColorName} from './utils';

export const DEFAULT_TAG_ICON = 'tag';

export type TagProps = {
  label: string;
  color?: TagColorName;
  showIcon?: boolean;
};
export const Tag: FC<TagProps> = ({label, color, showIcon = false}) => {
  return (
    <Tailwind>
      <div
        key={`tag-${label}`}
        className={classNames(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-[3px] text-[14px]',
          showIcon ? 'pl-4 pr-6' : 'px-6',
          getTagColor(color)
        )}>
        {showIcon && (
          <Icon className="mr-4 h-14 w-14" name={DEFAULT_TAG_ICON} />
        )}
        <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
          {label}
        </span>
      </div>
    </Tailwind>
  );
};

export type RemovableTagProps = {
  label: string;
  removeAction: ReactElement<typeof RemoveAction>;
  color?: TagColorName;
  showIcon?: boolean;
};
export const RemovableTag: FC<RemovableTagProps> = ({
  label,
  removeAction,
  color,
  showIcon = false,
}) => {
  return (
    <Tailwind>
      <div
        key={`tag-${label}`}
        className={classNames(
          'night-aware',
          'min-h-22 flex max-h-22 w-fit items-center rounded-[3px] text-[14px]',
          getTagColor(color),
          showIcon ? 'px-4' : 'pl-6 pr-4'
        )}>
        {showIcon && (
          <Icon className="mr-4 h-14 w-14" name={DEFAULT_TAG_ICON} />
        )}
        <span className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap">
          {label}
        </span>
        {removeAction}
      </div>
    </Tailwind>
  );
};
