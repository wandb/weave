import Autocomplete, {AutocompleteProps} from '@mui/material/Autocomplete';
import {createTheme, ThemeProvider} from '@mui/material/styles';
import React from 'react';

import {
  MOON_100,
  MOON_250,
  MOON_500,
  MOON_800,
  TEAL_300,
  TEAL_400,
  TEAL_500,
  TEAL_600,
  MOON_900,
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
              overflow: 'hidden',
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
              '&:hover fieldset': {
                borderColor: hexToRGB(TEAL_500, 0.4),
                borderWidth: '2px',
              },
              '& input::placeholder': {
                color: MOON_500,
                opacity: 1,
              },
              // Pseudo-element for hover effect without clipping the border
              '&::before': {
                content: '""',
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                border: '2px solid transparent',
                borderRadius: '4px',
                pointerEvents: 'none',
              },
              '&:hover::before': {
                borderColor: hexToRGB(TEAL_500, 0.4),
              },
              '&.Mui-focused::before': {
                borderColor: TEAL_400,
              },
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
          // menu dropdown
          paper: {
            border: `1px solid ${MOON_250}`,
            borderRadius: '4px',
            boxShadow: '0 12px 24px rgba(0, 0, 0, 0.16)',
            // we invert in dark mode automatically unless we want
            //to use night-aware and override all other styles. so moon_100 == moon_900
            backgroundColor: props.isDarkMode ? MOON_100 : 'white',
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
