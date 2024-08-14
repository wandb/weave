/**
 * Select from a list of calls.
 */

import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {StyledPaper} from '../StyledAutocomplete';
import {StyledTextField} from '../StyledTextField';

const Option = styled.li`
  display: flex;
  align-items: center;
`;
Option.displayName = 'S.Option';

export const OptionLabel = styled.div`
  flex: 1 1 auto;
  font-family: monospace;
  font-size: 0.8em;
`;
OptionLabel.displayName = 'S.OptionLabel';

type SelectCallProps = {
  calls: string[];

  valueId: string;

  onChange: (callId: string) => void;
};

export const SelectCall = ({calls, valueId, onChange}: SelectCallProps) => {
  const options = calls.sort().map(callId => ({
    id: callId,
    label: callId,
  }));
  const value = options.find(o => o.id === valueId);
  return (
    <Autocomplete
      options={options}
      size="small"
      sx={{width: 380}}
      disableClearable
      renderInput={params => <StyledTextField {...params} />}
      PaperComponent={paperProps => <StyledPaper {...paperProps} />}
      value={value}
      onChange={(_, newValue) => {
        onChange(newValue.id);
      }}
      renderOption={(props, option) => {
        return (
          <Option {...props}>
            <OptionLabel>{option.id}</OptionLabel>
          </Option>
        );
      }}
    />
  );
};
