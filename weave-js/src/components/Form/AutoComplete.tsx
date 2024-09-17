import {Paper, PaperProps} from '@mui/material';
import Autocomplete, {AutocompleteProps} from '@mui/material/Autocomplete';
import {createTheme, ThemeProvider} from '@mui/material/styles';
import React from 'react';

import {
  MOON_100,
  MOON_250,
  MOON_500,
  MOON_800,
  TEAL_300,
  TEAL_350,
  TEAL_400,
  TEAL_600,
} from '../../common/css/color.styles';
import {hexToRGB} from '../../common/css/globals.styles';

const HEIGHTS = {
  small: '24px',
  medium: '32px',
  large: '40px',
  variable: undefined,
};

const FONT_SIZES = {
  small: '14px',
  medium: '16px',
  large: '16px',
  variable: '14px',
};

const PADDING = {
  small: '2px 8px',
  medium: '4px 6px 4px 12px',
  large: '8px 12px',
  variable: '2px 8px',
};

const getStyles = (props: AdditionalProps) => {
  const size = props.size ?? 'medium';
  const customTheme = createTheme({
    components: {
      MuiAutocomplete: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              height: HEIGHTS[size],
              padding: PADDING[size],
              fontSize: FONT_SIZES[size],
              fontFamily: 'Source Sans Pro',
              minWidth: '100px',
              color: MOON_800,
              maxWidth: props.maxWidth ? `${props.maxWidth}px` : '100%',
              '&& fieldset': {
                borderColor: MOON_250,
              },
              '&.Mui-focused fieldset': {
                borderColor: TEAL_400,
                borderWidth: '2px',
              },
              '& .MuiInputBase-input': {
                whiteSpace: 'nowrap',
                textOverflow: 'ellipsis',
              },
              '&.MuiOutlinedInput-root:hover:not(.Mui-focused) fieldset': {
                borderColor: TEAL_350,
                borderWidth: '2px',
              },
              '& input::placeholder': {
                color: MOON_500,
                opacity: 1,
              },
            },
            '&.MuiAutocomplete-hasPopupIcon .MuiOutlinedInput-root, &.MuiAutocomplete-hasClearIcon .MuiOutlinedInput-root':
              {
                paddingRight: props.showEndIcon ? '28px' : '0px', // Apply padding only if input exists
              },
          },
          option: {
            borderColor: MOON_250,
            borderWidth: '1px',
            paddingLeft: '10px !important',
            margin: '0 6px',
            borderRadius: '4px',
            cursor: 'pointer',
            backgroundColor: 'transparent',
            color: MOON_800,
            fontSize: FONT_SIZES[size],
            '&[aria-selected="true"]': {
              backgroundColor: `${hexToRGB(TEAL_300, 0.32)} !important`,
              color: TEAL_600,
            },
            '&.Mui-focused[aria-selected="true"]': {
              backgroundColor: `${hexToRGB(TEAL_300, 0.32)} !important`,
              color: TEAL_600,
            },
            '&:hover': {
              backgroundColor: MOON_100,
            },
          },
          clearIndicator: {
            overflow: 'hidden',
            borderRadius: '4px',
            width: '24px',
            height: '24px',
            '&:hover': {
              backgroundColor: '#f5f5f5',
            },
          },
          endAdornment: {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          },
          // menu dropdown
          paper: {
            boxShadow: '0 12px 24px rgba(0, 0, 0, 0.16)',
            // MOON_100 is inverted to MOON_900 in dark mode automatically
            // this is a nice hack that lets us avoid setting night-aware and
            // attempting to override individual styles
            backgroundColor: props.isDarkMode ? MOON_100 : 'white',
            border: `1px solid ${MOON_250}`,
            borderRadius: '4px',
          },
        },
      },
    },
  });
  return customTheme;
};
const SelectSizes = {
  Small: 'small',
  Medium: 'medium',
  Large: 'large',
  Variable: 'variable',
} as const;

type SelectSize = (typeof SelectSizes)[keyof typeof SelectSizes];

type AdditionalProps = {
  size?: SelectSize;
  isDarkMode?: boolean;
  maxWidth?: number;
  showEndIcon?: boolean;
};

export const AutoComplete = <Option,>(
  props: AutocompleteProps<Option, boolean, boolean, boolean> & AdditionalProps
) => {
  return (
    <ThemeProvider theme={getStyles(props)}>
      <Autocomplete {...props} />
    </ThemeProvider>
  );
};
