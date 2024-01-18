import {Chip} from '@mui/material';
import React from 'react';

export const CallStatusCodeChip: React.FC<{
  statusCode: 'SUCCESS' | 'ERROR' | 'UNSET';
  showLabel?: boolean;
}> = ({statusCode, showLabel}) => {
  return (
    <Chip
      label={showLabel ? statusCode : ' '}
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
