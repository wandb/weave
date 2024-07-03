import {Box, BoxProps} from '@material-ui/core';
import React from 'react';

import {STANDARD_PADDING} from './ecpConstants';

export const VerticalBox: React.FC<BoxProps> = props => {
  return (
    <Box
      {...props}
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gridGap: STANDARD_PADDING,
        overflow: 'hidden',
        flex: '0 0 auto',
        ...props.sx,
      }}
    />
  );
};

export const HorizontalBox: React.FC<BoxProps> = props => {
  return (
    <Box
      {...props}
      sx={{
        display: 'flex',
        flexDirection: 'row',
        gridGap: STANDARD_PADDING,
        overflow: 'hidden',
        flex: '0 0 auto',
        ...props.sx,
      }}
    />
  );
};
