import {Autocomplete, CircularProgress, TextField} from '@mui/material';
import React, {FC, useMemo} from 'react';

import * as Queries from '../query';

export const ProjectNamePicker: FC<{
  entityName: string;
  value: string | null;
  setValue: (newValue: string | null) => void;
}> = ({entityName, value, setValue}) => {
  const query = Queries.useProjectsForEntity(entityName);
  const loading = query.loading;
  const values = useMemo(() => query.result ?? [], [query.result]);
  return (
    <Autocomplete
      value={value}
      onChange={(event: any, newValue: string | null) => {
        setValue(newValue);
      }}
      options={values}
      renderInput={params => (
        <TextField
          {...params}
          label="Project"
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
    />
  );
};
