import React from 'react';

import {Paper as MaterialPaper} from '@mui/material';

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
