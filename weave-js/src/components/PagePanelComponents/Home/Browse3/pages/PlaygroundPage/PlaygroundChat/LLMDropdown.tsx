import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {LLM_MAX_TOKENS, LLMMaxTokensKey} from '../llmMaxTokens';

interface LLMDropdownProps {
  value: LLMMaxTokensKey;
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({value, onChange}) => {
  const options: Array<{value: LLMMaxTokensKey; label: LLMMaxTokensKey}> =
    Object.keys(LLM_MAX_TOKENS).map(llm => ({
      value: llm as LLMMaxTokensKey,
      label: llm as LLMMaxTokensKey,
    }));

  return (
    <Box
      sx={{
        width: 'max-content',
        maxWidth: '100%',
        '& .MuiOutlinedInput-root': {
          width: 'max-content',
          maxWidth: '200px',
        },
        '& > div': {
          width: 'max-content',
          maxWidth: '200px',
        },
        '& .MuiAutocomplete-popper, & [class*="-menu"]': {
          width: '300px !important',
        },
        '& #react-select-2-listbox': {
          width: '300px',
          maxHeight: '500px',
        },
        '& #react-select-2-listbox > div': {
          maxHeight: '500px',
          width: '300px',
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
            onChange((option as {value: LLMMaxTokensKey}).value, maxTokens);
          }
        }}
        options={options}
        size="medium"
        isSearchable
      />
    </Box>
  );
};
