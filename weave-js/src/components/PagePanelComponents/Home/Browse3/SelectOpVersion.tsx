import {Autocomplete, TextField} from '@mui/material';
import {MOON_500} from '@wandb/weave/common/css/globals.styles';
import React from 'react';
import styled from 'styled-components';

import {Pill} from '../../../Tag';
import {Timestamp} from '../../../Timestamp';
import {
  opVersionKeyToRefUri,
  OpVersionSchema,
} from './pages/wfReactInterface/interface';

const Option = styled.li`
  display: flex;
  align-items: center;
`;
Option.displayName = 'S.Option';

export const OptionLabel = styled.div`
  flex: 1 1 auto;
`;
OptionLabel.displayName = 'S.OptionLabel';

export const OptionTimestamp = styled.div`
  color: ${MOON_500};
  font-size: 12px;
`;
OptionTimestamp.displayName = 'S.OptionTimestamp';

type SelectOpVersionProps = {
  opVersions: OpVersionSchema[];

  valueURI: string;

  // Op page we are currently viewing, not value of the select
  currentVersionURI: string;

  onChange: (uri: string) => void;
};

export const SelectOpVersion = ({
  opVersions,
  valueURI,
  currentVersionURI,
  onChange,
}: SelectOpVersionProps) => {
  const options = opVersions.map(opv => ({
    id: opVersionKeyToRefUri(opv),
    label: 'v' + opv.versionIndex,
    created: opv.createdAtMs,
    isCurrent: opVersionKeyToRefUri(opv) === currentVersionURI,
  }));
  const value = options.find(o => o.id === valueURI);
  return (
    <Autocomplete
      options={options}
      size="small"
      sx={{width: 260}}
      disableClearable
      renderInput={params => <TextField {...params} />}
      value={value}
      onChange={(_, newValue) => {
        onChange(newValue.id);
      }}
      renderOption={(props, option) => {
        return (
          <Option {...props}>
            <OptionLabel>{option.label}</OptionLabel>
            {option.isCurrent && (
              <Pill color="blue" label="Current" className="mr-12" />
            )}
            <OptionTimestamp>
              <Timestamp value={option.created / 1000} />
            </OptionTimestamp>
          </Option>
        );
      }}
    />
  );
};
