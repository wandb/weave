import {styled} from '@mui/material/styles';
import {DateTimePicker, DateTimePickerProps} from '@mui/x-date-pickers';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import moment from 'moment';
import React from 'react';

const COLOR_BORDER_OVER = hexToRGB(Colors.TEAL_500, 0.4);
const COLOR_BG_SELECTED_TEXT = Colors.MOON_100;

export const StyledDateTimePicker = styled(
  (props: DateTimePickerProps<moment.Moment>) => <DateTimePicker {...props} />
)(() => ({
  '& .MuiOutlinedInput-root': {
    fontFamily: 'Source Sans Pro',
    padding: 4,
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
}));
