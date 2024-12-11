import React, {memo} from 'react';
import {LegacyWBIcon, LegacyWBIconProps} from './LegacyWBIcon';

export type WBIconProps = LegacyWBIconProps;

const WBIconComponent: React.FC<WBIconProps> = props => {
  return <LegacyWBIcon {...props} />;
};

export const WBIcon = memo(WBIconComponent);
