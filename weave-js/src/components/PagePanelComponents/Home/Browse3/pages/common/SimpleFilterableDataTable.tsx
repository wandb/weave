import {Box, SxProps} from '@mui/material';
import React from 'react';

export const FilterLayoutTemplate: React.FC<{
  filterPopoutTargetUrl?: string;
  showFilterIndicator?: boolean;
  showPopoutButton?: boolean;
  filterListItems?: React.ReactNode;
  filterListSx?: SxProps;
}> = props => {
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
      }}>
      {props.filterListItems && (
        <Box
          sx={{
            flex: '0 0 auto',
            width: '100%',
            maxWidth: '100%',
            minHeight: 50,
            transition: 'width 0.1s ease-in-out',
            display: 'flex',
            flexDirection: 'row',
            overflowX: 'auto',
            overflowY: 'hidden',
            alignItems: 'center',
            gap: '8px',
            px: '16px',
            py: '8px',
            '& li': {
              padding: 0,
              minWidth: '200px',
            },
            '& input, & label, & .MuiTypography-root': {
              fontSize: '0.875rem',
            },
            ...(props.filterListSx ?? {}),
          }}>
          {props.filterListItems}
        </Box>
      )}
      {props.children}
    </Box>
  );
};
