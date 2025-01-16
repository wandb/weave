import React, {ReactNode} from 'react';

import {Alert} from '../../../../../Alert';

type TabUseBannerProps = {
  children?: ReactNode | undefined;
};

const STYLE_BANNER = {
  fontSize: 14,
};

export const TabUseBanner = ({children}: TabUseBannerProps) => {
  return (
    <Alert icon="lightbulb-info" style={STYLE_BANNER}>
      {children}
    </Alert>
  );
};
