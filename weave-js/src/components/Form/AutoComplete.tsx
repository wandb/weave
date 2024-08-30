import React, {FC, SyntheticEvent, useState} from 'react';
import Autocomplete, {AutocompleteProps} from '@mui/material/Autocomplete';
import TextField from '@mui/material/TextField';
import {
  TEAL_500,
  TEAL_600,
  TEAL_300,
  MOON_100,
  MOON_800,
  MOON_250,
  MOON_500,
} from '../../common/css/color.styles';
import {hexToRGB} from '../../common/css/globals.styles';
import {createTheme, styled, ThemeProvider} from '@mui/material/styles';
import Box from '@mui/material/Box';

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

const getStyles = <Option,>(props: AdditionalProps) => {
  const size = props.size ?? 'medium';
  const customTheme = createTheme({
    components: {
      MuiTextField: {
        styleOverrides: {
          root: {
            '& .MuiInputBase-input::placeholder': {
              color: MOON_500,
              fontSize: '16px',
              opacity: 1,
              fontFamily: 'Source Sans Pro',
            },
          },
        },
      },
      MuiAutocomplete: {
        styleOverrides: {
          clearIndicator: {
            visibility: 'visible',
            opacity: 1,
            borderRadius: '4px',
            width: '24px',
            height: '24px',
          },
          hasClearIcon: {
            '& .MuiAutocomplete-clearIndicator': {
              visibility: 'visible',
              opacity: 1,
            },
          },
          option: {
            padding: '6px 10px',
            margin: '0 6px',
            display: '-webkit-box',
            WebkitBoxOrient: 'vertical',
            WebkitLineClamp: 5,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'normal',
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
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            height: HEIGHTS[size],
            padding: '4px 12px',
            fontSize: '16px',
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

export const AutoComplete = <Option, multiple, disableClearable, freeSolo>(
  props: AutocompleteProps<Option, boolean, boolean, boolean> & AdditionalProps
) => {
  return (
    <ThemeProvider theme={getStyles(props)}>
      <Autocomplete {...props} />
    </ThemeProvider>
  );
};
