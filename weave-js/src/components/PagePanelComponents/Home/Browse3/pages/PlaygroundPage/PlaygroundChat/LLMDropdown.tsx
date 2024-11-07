import {MenuItem, TextField} from '@mui/material';
import {MOON_250, TEAL_400} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React from 'react';

import {LLM_MAX_TOKENS} from './llmMaxTokens';

interface LLMDropdownProps {
  value: string;
  onChange: (value: string, maxTokens: number) => void;
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({value, onChange}) => {
  const handleChange = (
    event: React.SyntheticEvent,
    newValue: string | null
  ) => {
    if (newValue) {
      const maxTokens =
        LLM_MAX_TOKENS[newValue as keyof typeof LLM_MAX_TOKENS]?.max_tokens ||
        0;
      onChange(newValue, maxTokens);
    }
  };

  return (
    <TextField
      select
      value={value}
      onChange={e => handleChange(e, e.target.value)}
      size="small"
      slotProps={{
        select: {
          IconComponent: props => <Icon {...props} name="chevron-down" />,
        },
      }}
      sx={{
        width: '100%',
        minWidth: '100px',
        height: '32px',
        padding: 0,
        fontFamily: 'Source Sans Pro',
        fontSize: '16px',
        '& .MuiSelect-select': {
          fontFamily: 'Source Sans Pro',
          fontSize: '16px',
          height: '16px',
        },
        '& .MuiMenuItem-root': {
          fontFamily: 'Source Sans Pro',
          fontSize: '16px',
        },
        '& .MuiInputBase-root': {
          height: '32px',
          paddingY: '4px',
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
      {Object.keys(LLM_MAX_TOKENS).map(llmWithToken => (
        <MenuItem key={llmWithToken} value={llmWithToken}>
          {llmWithToken}
        </MenuItem>
      ))}
    </TextField>
  );
};
