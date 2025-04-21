import React, {ReactElement} from 'react';
import {twMerge} from 'tailwind-merge';

import {RemoveAction, useTagClasses} from '../../../../Tag';

export type FilterTagProps = {
  label: React.ReactNode;
  removeAction: ReactElement<typeof RemoveAction>;
  isEditing?: boolean;
  onClick?: () => void;
};

export const FilterTag = ({
  label,
  removeAction,
  isEditing = false,
  onClick,
}: FilterTagProps) => {
  const classes = useTagClasses({
    color: isEditing ? 'teal' : 'moon',
    isInteractive: true,
  });
  return (
    <div
      key={`tag-${label}`}
      className={twMerge(classes, 'pl-6 pr-4')}
      onClick={onClick}
      style={{cursor: onClick ? 'pointer' : 'default'}}>
      <div
        className={twMerge(
          'flex items-center overflow-hidden text-ellipsis whitespace-nowrap '
        )}>
        {label}
      </div>
      {removeAction}
    </div>
  );
};
