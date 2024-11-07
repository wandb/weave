import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {LLM_MAX_TOKENS} from '../llmMaxTokens';

interface LLMDropdownProps {
  value: string;
  onChange: (value: string, maxTokens: number) => void;
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({value, onChange}) => {
  const options = Object.keys(LLM_MAX_TOKENS).map(llm => ({
    value: llm,
    label: llm,
  }));

  return (
    <Box
      sx={{
        width: '150px',
        '& #react-select-2-listbox': {
          width: '300px',
          maxHeight: '500px',
        },
        '& #react-select-2-listbox > div': {
          maxHeight: '500px',
        },
      }}>
      <Select
        value={options.find(opt => opt.value === value)}
        onChange={option => {
          if (option) {
            const maxTokens =
              LLM_MAX_TOKENS[
                (option as {value: string}).value as keyof typeof LLM_MAX_TOKENS
              ]?.max_tokens || 0;
            onChange((option as {value: string}).value, maxTokens);
          }
        }}
        options={options}
        size="medium"
        isSearchable
      />
    </Box>
  );
};
