import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
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
  const options = RESPONSE_FORMATS.map(format => ({
    value: format,
    label: format,
  }));

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
      }}>
      <span style={{fontSize: '14px'}}>Response format</span>
      <Select
        value={options.find(opt => opt.value === responseFormat)}
        onChange={option => {
          if (option) {
            setResponseFormat(
              (option as {value: PlaygroundResponseFormats}).value
            );
          }
        }}
        options={options}
        size="medium"
      />
    </Box>
  );
};
