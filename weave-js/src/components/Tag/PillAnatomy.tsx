import React from 'react';
import { twMerge } from 'tailwind-merge';

import { Icon, IconName } from '../Icon';
import { Tailwind } from '../Tailwind';
import { getTagColorClass,TagColorName } from './utils';

export const Root = ({
  color,
  className,
  children,
}: {
  color?: TagColorName;
  className?: string;
  children?: React.ReactNode;
}) => {
  return (
    <Tailwind>
      <div
        className={twMerge(
          'night-aware',
          'min-h-22 flex h-22 max-h-22 w-fit items-center rounded-2xl',
          getTagColorClass(color),
          className
        )}>
        <>{children}</>{' '}
      </div>
    </Tailwind>
  );
};

export const Indicator = ({icon}: {icon: IconName}) => {
  return <Icon className="m-4 h-14 w-14" name={icon} />;
};

export const Label = ({text}: {text: string}) => {
  return (
    <p className="max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap text-sm">
      {text}
    </p>
  );
};
