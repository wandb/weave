import {styled} from '@mui/material/styles';
import {DataGridPro, DataGridProProps} from '@mui/x-data-grid-pro';
import {gridClasses} from '@mui/x-data-grid-pro';
import React from 'react';

import {
  Color,
  hexToRGB,
  MOON_50,
  MOON_500,
  OBLIVION,
  RED_300,
  TEAL_300,
  WHITE,
} from '../../../../common/css/globals.styles';
import {Loading} from '../../../Loading';

// Class name constants
export const SELECTED_FOR_DELETION = 'selected-for-deletion';

// TODO: Handle night mode
const backgroundColorHovered = hexToRGB(OBLIVION, 0.04);
const backgroundColorSelected = hexToRGB(TEAL_300, 0.32);
const backgroundColorHoveredSelected = Color.fromHex(WHITE)
  .blend(Color.fromHex(TEAL_300, 0.32))
  .blend(Color.fromHex(OBLIVION, 0.04))
  .toString();
const backgroundColorSelectedForDeletion = hexToRGB(RED_300, 0.32);

// Use our custom loading component that matches our palette.
const LoadingOverlay = () => <Loading centered />;

export const StyledDataGrid = styled(
  ({
    keepBorders,
    ...otherProps
  }: DataGridProProps & {keepBorders?: boolean}) => {
    const slots = otherProps.slots ?? {};
    if (!slots.loadingOverlay) {
      slots.loadingOverlay = LoadingOverlay;
    }
    return <DataGridPro slots={slots} {...otherProps} />;
  }
)(({keepBorders}) => ({
  ...(!keepBorders ? {borderRight: 0, borderLeft: 0, borderBottom: 0} : {}),

  fontFamily: 'Source Sans Pro',

  '& .MuiDataGrid-columnHeaders': {
    backgroundColor: MOON_50,
    color: MOON_500,
  },

  '& .MuiDataGrid-pinnedColumnHeaders': {
    backgroundColor: MOON_50,
    color: MOON_500,
  },

  '& .MuiDataGrid-columnHeaderTitle': {
    fontWeight: 600,
  },

  '& .MuiDataGrid-columnHeader:focus, .MuiDataGrid-cell:focus': {
    outline: 'none',
  },

  '& .MuiTablePagination-displayedRows': {
    margin: 0,
  },

  '& .MuiTablePagination-actions': {
    marginRight: '16px',
  },

  [`& .${gridClasses.row}`]: {
    '&.Mui-hovered': {
      backgroundColor: backgroundColorHovered,
    },
    '&.Mui-selected': {
      backgroundColor: backgroundColorSelected,
      '&.Mui-hovered': {
        backgroundColor: backgroundColorHoveredSelected,
      },
    },
    [`&.${SELECTED_FOR_DELETION}`]: {
      backgroundColor: backgroundColorSelectedForDeletion,
      '&.Mui-hovered': {
        backgroundColor: backgroundColorSelectedForDeletion,
      },
    },
  },
}));
