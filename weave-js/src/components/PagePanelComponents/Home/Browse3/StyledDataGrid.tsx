import {styled} from '@mui/material/styles';
import {DataGridPro} from '@mui/x-data-grid-pro';
import {gridClasses} from '@mui/x-data-grid-pro';

import {
  Color,
  hexToRGB,
  MOON_50,
  OBLIVION,
  TEAL_300,
  WHITE,
} from '../../../../common/css/globals.styles';

// TODO: Handle night mode
const backgroundColorHovered = hexToRGB(OBLIVION, 0.04);
const backgroundColorSelected = hexToRGB(TEAL_300, 0.32);
const backgroundColorHoveredSelected = Color.fromHex(WHITE)
  .blend(Color.fromHex(TEAL_300, 0.32))
  .blend(Color.fromHex(OBLIVION, 0.04))
  .toString();

export const StyledDataGrid = styled(DataGridPro)(({theme}) => ({
  borderRight: 0,
  borderLeft: 0,
  borderBottom: 0,

  '& .MuiDataGrid-columnHeaders': {
    backgroundColor: MOON_50,
    color: '#979a9e',
  },

  '& .MuiDataGrid-columnHeader:focus, .MuiDataGrid-cell:focus': {
    outline: 'none',
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
  },
}));
