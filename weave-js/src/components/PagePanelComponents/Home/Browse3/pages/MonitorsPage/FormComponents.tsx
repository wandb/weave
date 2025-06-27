import {Typography} from '@mui/material';
import React from 'react';

export const typographyStyle = {fontFamily: 'Source Sans Pro'};

export const FieldName = ({name}: {name: string}) => {
  return (
    <Typography sx={typographyStyle} className="mb-8 font-semibold">
      {name}
    </Typography>
  );
};
