/**
 * Override the grid column menu to not show the "Manage columns" item
 * as we implement our own UI outside the grid for this. We still want the "Hide column" item,
 * which is inconveniently tied to the "Manage columns" item in `columnMenuColumnsItem`.
 */
import {createTheme, ThemeProvider} from '@mui/material/styles';
import {
  GridColumnMenu,
  GridColumnMenuHideItem,
  GridColumnMenuProps,
} from '@mui/x-data-grid-pro';
import React from 'react';

type Slots = Record<string, React.JSXElementConstructor<any> | null>;

const columnMenuTheme = createTheme({
  components: {
    MuiTypography: {
      styleOverrides: {
        root: {
          fontSize: '14px',
          fontFamily: 'Source Sans Pro',
          fontWeight: 400,
        },
      },
    },
  },
});
export const CallsCustomColumnMenu = (props: GridColumnMenuProps) => {
  const slots: Slots = {columnMenuColumnsItem: null};
  if (props.colDef.hideable ?? true) {
    slots.columnMenuUserItem = GridColumnMenuHideItem;
  }
  return (
    <ThemeProvider theme={columnMenuTheme}>
      <GridColumnMenu {...props} slots={slots} />
    </ThemeProvider>
  );
};
