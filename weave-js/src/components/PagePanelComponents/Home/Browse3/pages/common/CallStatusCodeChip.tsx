import {Chip} from '@mui/material';
import React from 'react';

const ensureCapitalizedFirstLetter = (str: string) => {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

export const CallStatusCodeChip: React.FC<{
  statusCode: 'SUCCESS' | 'ERROR' | 'UNSET';
  showLabel?: boolean;
}> = ({statusCode, showLabel}) => {
  return (
    <Chip
      label={showLabel ? ensureCapitalizedFirstLetter(statusCode) : ' '}
      sx={{height: '20px', lineHeight: 2}}
      size="small"
      color={
        statusCode === 'SUCCESS'
          ? 'success'
          : statusCode === 'ERROR'
          ? 'error'
          : undefined
      }
    />
  );
};
