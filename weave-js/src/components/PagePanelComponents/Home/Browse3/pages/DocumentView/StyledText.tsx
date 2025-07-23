import {Typography} from '@mui/material';
import React from 'react';

export const Header = ({children}: {children: string}) => (
  <Typography
    variant="body1"
    sx={{
      fontSize: '16px',
      fontWeight: 600,
      color: 'text.primary',
      fontFamily: 'Source Sans Pro',
    }}>
    {children}
  </Typography>
);

export const Subheader = ({children}: {children: string}) => (
  <Typography
    variant="body2"
    sx={{
      fontSize: '14px',
      fontWeight: 600,
      color: 'text.secondary',
      fontFamily: 'Source Sans Pro',
    }}>
    {children}
  </Typography>
);

export const Body = ({children}: {children: string}) => (
  <Typography
    variant="body2"
    sx={{
      fontSize: '16px',
      fontWeight: 400,
      color: 'text.primary',
      fontFamily: 'Source Sans Pro',
    }}>
    {children}
  </Typography>
);

export const TitleRow = ({children}: {children: React.ReactElement}) => (
  <div style={{display: 'flex', alignItems: 'center', marginBottom: '4px'}}>
    {children}
  </div>
);
