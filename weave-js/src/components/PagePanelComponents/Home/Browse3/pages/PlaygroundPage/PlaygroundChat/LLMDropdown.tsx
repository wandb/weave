import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {
  LLM_MAX_TOKENS,
  LLM_PROVIDER_LABELS,
  LLM_PROVIDERS,
  LLMMaxTokensKey,
} from '../llmMaxTokens';

interface LLMDropdownProps {
  value: LLMMaxTokensKey;
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({value, onChange}) => {
  const options = LLM_PROVIDERS.map(provider => ({
    // for each provider, get all the LLMs that are supported by that provider
    label: LLM_PROVIDER_LABELS[provider],
    // filtering to the LLMs that are supported by that provider
    options: Object.keys(LLM_MAX_TOKENS)
      .reduce<Array<{group: string; label: string; value: string}>>(
        (acc, llm) => {
          if (LLM_MAX_TOKENS[llm as LLMMaxTokensKey].provider === provider) {
            acc.push({
              group: provider,
              // add provider to the label if the LLM is not already prefixed with it
              label: llm.includes(provider) ? llm : provider + '/' + llm,
              value: llm,
            });
          }
          return acc;
        },
        []
      )
      .sort((a, b) => a.label.localeCompare(b.label)),
  }));

  return (
    <Box
      sx={{
        width: 'max-content',
        maxWidth: '100%',
        '& .MuiOutlinedInput-root': {
          width: 'max-content',
          maxWidth: '300px',
        },
        '& > div': {
          width: 'max-content',
          maxWidth: '300px',
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
        value={options.flatMap(o => o.options).find(o => o.value === value)}
        onChange={option => {
          if (option) {
            const maxTokens =
              LLM_MAX_TOKENS[option.value as LLMMaxTokensKey]?.max_tokens || 0;
            onChange(option.value as LLMMaxTokensKey, maxTokens);
          }
        }}
        options={options}
        size="medium"
        isSearchable
      />
    </Box>
  );
};
