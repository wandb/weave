import {Autocomplete} from '@mui/material';
import _ from 'lodash';
import React from 'react';
import styled from 'styled-components';

import {ObjectVersionSchema} from '../pages/wfReactInterface/wfDataModelHooksInterface';
import {StyledPaper} from '../StyledAutocomplete';
import {StyledTextField} from '../StyledTextField';

const Option = styled.li`
  display: flex;
  align-items: center;
`;
Option.displayName = 'S.Option';

export const OptionLabel = styled.div`
  flex: 1 1 auto;
`;
OptionLabel.displayName = 'S.OptionLabel';

type SelectObjProps = {
  objVersions: ObjectVersionSchema[];

  valueId: string;

  onChange: (versionId: string) => void;
};

export const SelectObj = ({objVersions, valueId, onChange}: SelectObjProps) => {
  const options = _.sortBy(
    objVersions.map(objv => ({
      id: objv.objectId,
      label: objv.objectId,
    })),
    'id'
  );
  const value = options.find(o => o.id === valueId);
  return (
    <Autocomplete
      options={options}
      size="small"
      sx={{width: 260}}
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
