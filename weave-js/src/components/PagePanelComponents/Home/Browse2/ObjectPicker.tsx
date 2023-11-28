import {CircularProgress, TextField} from '@mui/material';
import Autocomplete, {createFilterOptions} from '@mui/material/Autocomplete';
import React, {FC, useMemo} from 'react';

import * as Queries from '../query';

export interface ChosenObjectNameOption {
  name: string;
  isNew?: boolean;
}

const filterOptions = createFilterOptions<ChosenObjectNameOption>();

// A lot of this is from the Material UI Autocomplete docs
// Requires boilerplate make it so we can have a "Create New: ..." option.

export const ObjectNamePicker: FC<{
  entityName: string;
  projectName: string | null;
  rootType: string;
  value: ChosenObjectNameOption | null;
  setChosenObjectName: (newValue: ChosenObjectNameOption | null) => void;
}> = ({entityName, projectName, rootType, value, setChosenObjectName}) => {
  const query = Queries.useProjectObjectsOfType(
    entityName,
    projectName ?? '',
    rootType
  );
  const loading = query.loading;
  const options: ChosenObjectNameOption[] = useMemo(
    () => (query.result.map(v => v.name) ?? []).map(name => ({name})),
    [query.result]
  );
  return (
    <Autocomplete
      freeSolo
      selectOnFocus
      clearOnBlur
      handleHomeEndKeys
      value={value}
      onChange={(event, newValue) => {
        if (typeof newValue === 'string') {
          const isNew =
            options.find(option => option.name === newValue) == null;
          setChosenObjectName({name: newValue, isNew});
        } else {
          setChosenObjectName(newValue);
        }
      }}
      options={options}
      filterOptions={(innerOptions, params) => {
        const filtered = filterOptions(innerOptions, params);

        const {inputValue} = params;
        // Suggest the creation of a new value
        const isExisting = innerOptions.some(
          option => inputValue === option.name
        );
        if (inputValue !== '' && !isExisting) {
          filtered.push({
            name: inputValue,
            isNew: true,
          });
        }

        return filtered;
      }}
      renderInput={params => (
        <TextField
          {...params}
          disabled={!projectName}
          label={rootType}
          InputProps={{
            ...params.InputProps,
            endAdornment: (
              <React.Fragment>
                {loading ? (
                  <CircularProgress color="inherit" size={20} />
                ) : null}
                {params.InputProps.endAdornment}
              </React.Fragment>
            ),
          }}
        />
      )}
      getOptionLabel={option => {
        if (typeof option === 'string') {
          return option;
        } else {
          return option.name;
        }
      }}
      renderOption={(props, option) => {
        return (
          <li {...props}>
            {option.isNew
              ? `Create ${rootType}: "${option.name}"`
              : option.name}
          </li>
        );
      }}
    />
  );
};
