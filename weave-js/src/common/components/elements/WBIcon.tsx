import React, {memo} from 'react';

import {LegacyWBIcon, LegacyWBIconProps} from './LegacyWBIcon';

// Extend the IconSizeProp to include 'medium', which will be mapped to 'small'
export type WBIconSize = LegacyWBIconProps['size'] | 'medium';

export interface WBIconProps extends Omit<LegacyWBIconProps, 'size'> {
  size?: WBIconSize;
}

const WBIconComponent: React.FC<WBIconProps> = ({size, ...props}) => {
  // Map 'medium' size to 'small' for backward compatibility
  const mappedSize = size === 'medium' ? 'small' : size;
  return <LegacyWBIcon {...props} size={mappedSize} />;
};

export const WBIcon = memo(WBIconComponent);
