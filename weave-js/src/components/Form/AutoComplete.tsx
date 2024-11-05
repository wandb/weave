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

const getStyles = (props: AdditionalProps) => {
  const size = props.size ?? 'medium';
  const customTheme = createTheme({
    components: {
      MuiAutocomplete: {
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              paddingTop: '0px !important',
              paddingBottom: '0px !important',
              fontSize: FONT_SIZES[size],
              fontFamily: 'Source Sans Pro',
              color: MOON_800,
              maxWidth: props.maxWidth ? `${props.maxWidth}px` : '100%',
              minWidth: props.minWidth ? `${props.minWidth}px` : '100px',
              '& fieldset': {
                borderColor: MOON_250,
              },
              '&.Mui-focused fieldset': {
                borderColor: TEAL_400,
                borderWidth: '2px',
              },
              '&:hover:not(.Mui-focused) fieldset': {
                borderColor: TEAL_350,
                borderWidth: '2px',
              },
              '& .MuiInputBase-input::placeholder': {
                color: MOON_500,
                opacity: 1,
              },
              '& .MuiInputBase-input': {
                padding: '0px',
                minHeight: `${HEIGHTS[size]} !important`,
              },
            },
            '& .MuiAutocomplete-popupIndicator': {
              borderRadius: '4px',
              padding: '4px',
            },
            '&.MuiAutocomplete-hasPopupIcon .MuiOutlinedInput-root, &.MuiAutocomplete-hasClearIcon .MuiOutlinedInput-root':
              {
                paddingRight: props.hasInputValue ? '28px' : '0px', // Apply padding only if input exists
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
            '&:focus-within[aria-selected="true"]': {
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
          inputRoot: {
            '& .MuiInputBase-inputMultiline': {
              overflow: 'hidden',
              whiteSpace: 'pre-wrap',
              overflowY: 'auto',
              scrollbarWidth: 'none', // For Firefox (hides the scrollbar)
              msOverflowStyle: 'none', // For IE and Edge (hides the scrollbar)
              '&::-webkit-scrollbar': {
                display: 'none', // For Chrome, Safari, and WebKit-based browsers (hides the scrollbar)
              },
            },
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
  autocompleteRef?: React.MutableRefObject<HTMLDivElement | null>;
  hasInputValue?: boolean;
  isDarkMode?: boolean;
  maxWidth?: number;
  minWidth?: number;
  size?: SelectSize;
};

export const AutoComplete = <Option,>(
  props: AutocompleteProps<Option, boolean, boolean, boolean> & AdditionalProps
) => {
  const {
    autocompleteRef,
    hasInputValue,
    isDarkMode,
    maxWidth,
    minWidth,
    size,
    ...safeProps // we're just destructuring the other values out since they're unrecognized by the autocomplete component
  } = props;
  return (
    <ThemeProvider theme={getStyles(props)}>
      <Autocomplete ref={props.autocompleteRef} {...safeProps} />
    </ThemeProvider>
  );
};
