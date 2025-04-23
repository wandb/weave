/**
 * Small circle with icon.
 */
import React from 'react';

import {Icon, IconName} from '../../../../Icon';

type SmallRefIconProps = {
  icon: IconName;
};

export const SmallRefIcon = ({icon}: SmallRefIconProps) => {
  return (
    <div className="flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full bg-moon-300/[0.48]">
      <Icon role="presentation" className="h-[14px] w-[14px]" name={icon} />
    </div>
  );
};
