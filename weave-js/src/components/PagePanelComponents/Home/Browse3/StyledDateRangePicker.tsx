import {styled} from '@mui/material/styles';
import {DateRangePicker, DateRangePickerProps} from '@mui/x-date-pickers-pro';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import moment from 'moment';
import React from 'react';

const COLOR_BORDER_OVER = hexToRGB(Colors.TEAL_500, 0.4);
const COLOR_BG_SELECTED_TEXT = Colors.MOON_100;
const COLOR_BORDER_DEFAULT = Colors.MOON_300;

export const StyledDateRangePicker = styled(
  (props: DateRangePickerProps<moment.Moment>) => <DateRangePicker {...props} />
)(() => ({
  width: 'fit-content',

  '& .MuiOutlinedInput-root': {
    fontFamily: 'Source Sans Pro',
    padding: 4,
    // Set the default border color to the correct gray
    '& fieldset': {
      borderColor: COLOR_BORDER_DEFAULT,
      marginLeft: 8,
      marginBottom: 2,
    },
    '&:hover fieldset': {
      borderColor: COLOR_BORDER_OVER,
      borderWidth: 2,
    },
    '&.Mui-focused fieldset': {
      borderColor: COLOR_BORDER_OVER,
    },
    '& ::selection': {
      backgroundColor: COLOR_BG_SELECTED_TEXT,
    },
  },

  '& .MuiInputBase-input': {
    marginLeft: 12,
  },

  '& .MuiTypography-root': {
    display: 'none',
  },
}));
