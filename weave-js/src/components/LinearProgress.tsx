/**
 * Styled linear progress bar.
 */

import MuiLinearProgress, {
  LinearProgressProps as MuiLinearProgressProps,
} from '@mui/material/LinearProgress';
import React from 'react';

import * as Colors from '../common/css/color.styles';

export const LinearProgress = (props: MuiLinearProgressProps) => {
  return (
    <MuiLinearProgress
      {...props}
      sx={{
        backgroundColor: Colors.TEAL_300,
        '& .MuiLinearProgress-bar': {
          backgroundColor: Colors.TEAL_400,
        },
        height: 3, // Default is 4px
      }}
    />
  );
};
