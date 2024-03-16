import {Box} from '@mui/material';
import React from 'react';

import {WeaveAnimatedLoader} from '../../../../../Panel2/WeaveAnimatedLoader';

export const CenteredAnimatedLoader: React.FC = props => {
  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flex: '1 1 auto',
        justifyContent: 'center',
        alignItems: 'center',
      }}>
      <WeaveAnimatedLoader style={{height: '64px', width: '64px'}} />
    </Box>
  );
};
