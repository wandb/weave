import React, {ReactElement} from 'react';
import {twMerge} from 'tailwind-merge';

import {RemoveAction, useTagClasses} from '../../../../Tag';

export type FilterTagProps = {
  label: string;
  removeAction: ReactElement<typeof RemoveAction>;
};

export const FilterTag = ({label, removeAction}: FilterTagProps) => {
  const classes = useTagClasses({color: 'moon', isInteractive: true});
  return (
    <div key={`tag-${label}`} className={twMerge(classes, 'pl-6 pr-4')}>
      <p className={twMerge('overflow-hidden text-ellipsis whitespace-nowrap')}>
        {label}
      </p>
      {removeAction}
    </div>
  );
};
