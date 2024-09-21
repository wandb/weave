import React, {ReactElement} from 'react';
import {twMerge} from 'tailwind-merge';

import {RemoveAction, useTagClasses} from '../../../../Tag';

export type FilterTagProps = {
  label: React.ReactNode;
  removeAction: ReactElement<typeof RemoveAction>;
};

export const FilterTag = ({label, removeAction}: FilterTagProps) => {
  const classes = useTagClasses({color: 'moon', isInteractive: true});
  return (
    <div key={`tag-${label}`} className={twMerge(classes, 'pl-6 pr-4')}>
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
