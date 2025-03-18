import {styled} from '@mui/material/styles';
import {DateTimePicker, DateTimePickerProps} from '@mui/x-date-pickers';
import * as Colors from '@wandb/weave/common/css/color.styles';
import moment from 'moment';
import React from 'react';

const COLOR_BORDER_HOVER = Colors.TEAL_350;
const COLOR_BORDER_FOCUSED = Colors.TEAL_400;
const COLOR_BG_SELECTED_TEXT = Colors.MOON_100;
const COLOR_BORDER = Colors.MOON_250;

export const StyledDateTimePicker = styled(
  (props: DateTimePickerProps<moment.Moment>) => <DateTimePicker {...props} />
)(() => ({
  '& .MuiOutlinedInput-root': {
    fontFamily: 'Source Sans Pro',
    padding: 4,
    width: '202px',
    '& fieldset': {
      borderColor: COLOR_BORDER,
    },
    '&:hover fieldset': {
      borderColor: COLOR_BORDER_HOVER,
      borderWidth: 2,
      margin: -2,
    },
    '&.Mui-focused fieldset': {
      borderColor: COLOR_BORDER_FOCUSED,
      borderWidth: 2,
      margin: -2,
    },
    '& ::selection': {
      backgroundColor: COLOR_BG_SELECTED_TEXT,
    },
  },
}));
