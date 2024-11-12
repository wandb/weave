import {Box, MenuItem, TextField} from '@mui/material';
import {MOON_250, TEAL_400} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React from 'react';

import {PlaygroundResponseFormats} from '../types';

const RESPONSE_FORMATS: PlaygroundResponseFormats[] = Object.values(
  PlaygroundResponseFormats
);

type ResponseFormatEditorProps = {
  responseFormat: PlaygroundResponseFormats;
  setResponseFormat: (value: PlaygroundResponseFormats) => void;
};

export const ResponseFormatEditor: React.FC<ResponseFormatEditorProps> = ({
  responseFormat,
  setResponseFormat,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        pb: '4px',
      }}>
      <span>Response format</span>
      <TextField
        select
        value={responseFormat}
        onChange={e =>
          setResponseFormat(e.target.value as PlaygroundResponseFormats)
        }
        size="small"
        slotProps={{
          select: {
            IconComponent: props => <Icon {...props} name="chevron-down" />,
          },
        }}
        sx={{
          width: '100%',
          padding: 0,
          fontFamily: 'Source Sans Pro',
          fontSize: '16px',
          '& .MuiSelect-select': {
            fontFamily: 'Source Sans Pro',
            fontSize: '16px',
          },
          '& .MuiMenuItem-root': {
            fontFamily: 'Source Sans Pro',
            fontSize: '16px',
          },
          '& .MuiOutlinedInput-notchedOutline': {
            border: `1px solid ${MOON_250}`,
          },
          '& .Mui-focused .MuiOutlinedInput-notchedOutline': {
            border: `1px solid ${MOON_250}`,
          },
          '& .MuiOutlinedInput-root:hover .MuiOutlinedInput-notchedOutline': {
            border: `1px solid ${TEAL_400}`,
          },
        }}>
        {RESPONSE_FORMATS.map(format => (
          <MenuItem key={format} value={format}>
            {format}
          </MenuItem>
        ))}
      </TextField>
    </Box>
  );
};
