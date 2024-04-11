import {Paper, PaperProps} from '@mui/material';
import {styled} from '@mui/material/styles';
import * as Colors from '@wandb/weave/common/css/color.styles';
import {hexToRGB} from '@wandb/weave/common/css/utils';
import React from 'react';

const COLOR_BG_SELECTED = hexToRGB(Colors.TEAL_300, 0.32);
const COLOR_FG_SELECTED = Colors.TEAL_600;
const COLOR_BG_HOVER = Colors.MOON_100;

export const StyledPaper = styled((props: PaperProps) => <Paper {...props} />)(
  () => ({
    '& .MuiAutocomplete-option[aria-selected="true"].Mui-focused': {
      backgroundColor: COLOR_BG_SELECTED,
      color: COLOR_FG_SELECTED,
    },
    '& .MuiAutocomplete-option[aria-selected="true"]': {
      backgroundColor: COLOR_BG_SELECTED,
      color: COLOR_FG_SELECTED,
    },
    '& .MuiAutocomplete-option:hover': {
      backgroundColor: COLOR_BG_HOVER,
    },
  })
);
