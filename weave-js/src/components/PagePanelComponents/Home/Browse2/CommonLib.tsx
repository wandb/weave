import React from 'react';

import {Link as RouterLink} from 'react-router-dom';
import {Paper as MaterialPaper, Link as MaterialLink} from '@mui/material';

export const Link = (props: React.ComponentProps<typeof RouterLink>) => (
  <MaterialLink {...props} component={RouterLink} />
);

export const Paper = (props: React.ComponentProps<typeof MaterialPaper>) => {
  return (
    <MaterialPaper
      sx={{
        padding: theme => theme.spacing(2),
      }}
      {...props}>
      {props.children}
    </MaterialPaper>
  );
};
