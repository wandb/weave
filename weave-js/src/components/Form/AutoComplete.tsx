import Autocomplete, {AutocompleteProps} from '@mui/material/Autocomplete';
import {createTheme, ThemeProvider} from '@mui/material/styles';
import React from 'react';

import {
  MOON_100,
  MOON_250,
  MOON_500,
  MOON_800,
  TEAL_300,
  TEAL_500,
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
  medium: '4px 12px',
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
              color: MOON_800,
              '&& fieldset': {
                borderColor: MOON_250,
              },
              '&&:hover fieldset': {
                borderColor: hexToRGB(TEAL_500, 0.4),
                borderWidth: '2px',
              },
              '&&.Mui-focused fieldset': {
                borderColor: hexToRGB(TEAL_500, 0.64),
                borderWidth: '2px',
              },
              borderColor: MOON_250,
              '&:hover fieldset': {
                borderColor: hexToRGB(TEAL_500, 0.4),
                borderWidth: '2px',
              },
              '&.Mui-focused fieldset': {
                borderColor: hexToRGB(TEAL_500, 0.64),
                borderWidth: '2px',
              },
              '& input::placeholder': {
                color: MOON_500,
                opacity: 1,
              },
            },
          },
          option: {
            padding: '6px 10px',
            margin: '0 6px',
            borderRadius: '4px',
            cursor: 'pointer',
            backgroundColor: 'transparent',
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
            borderRadius: '4px',
            width: '24px',
            height: '24px',
            '&:hover': {
              backgroundColor: '#f5f5f5',
            },
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
