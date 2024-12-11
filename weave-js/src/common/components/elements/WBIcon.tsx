import React, {forwardRef, memo} from 'react';

import {LegacyWBIcon, LegacyWBIconProps} from './LegacyWBIcon';

// Extend the IconSizeProp to include 'medium', which will be mapped to 'small'
export type WBIconSize = LegacyWBIconProps['size'] | 'medium';

// Extend all props from LegacyWBIconProps except 'size' and 'ref' which we handle separately
export interface WBIconProps extends Omit<LegacyWBIconProps, 'size' | 'ref'> {
  size?: WBIconSize;
}

const WBIconComponent = forwardRef<HTMLElement, WBIconProps>(({size, ...props}, ref) => {
  // Map 'medium' size to 'small' for backward compatibility
  const mappedSize = size === 'medium' ? 'small' : size;
  return <LegacyWBIcon ref={ref} {...props} size={mappedSize} />;
});

WBIconComponent.displayName = 'WBIcon';

// Maintain the memo wrapper for performance optimization
export const WBIcon = memo(WBIconComponent);
