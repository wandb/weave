import {TextField, TextFieldProps} from '@mui/material';
import {styled} from '@mui/material/styles';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import React from 'react';

const COLOR_LABEL = Colors.TEAL_500;
const COLOR_BORDER_OVER = hexToRGB(Colors.TEAL_500, 0.4);
const COLOR_BG_SELECTED_TEXT = Colors.MOON_100;

export const StyledTextField = styled((props: TextFieldProps) => (
  <TextField {...props} />
))(() => ({
  '&:hover label': {
    color: COLOR_LABEL,
  },
  '& label.Mui-focused': {
    color: COLOR_LABEL,
  },
  '& .MuiOutlinedInput-root': {
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
