import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import { Box, TextField, TextFieldProps, Typography } from '@material-ui/core';
import { Icon, IconName } from '@wandb/weave/components/Icon';

export const LoadingSelect: typeof Select = props => {
  return <Select isDisabled placeholder="Loading..." {...props} />;
};


const FieldName: React.FC<{name: string, icon?: IconName}> = ({name, icon}) => {
  return (
    <Typography className="mb-8 font-semibold">
      {icon && <Icon name={icon} />}
      {name}
    </Typography>
  );
};

const WarningMessage: React.FC<{warning: string}> = ({warning}) => {
  return (
    <Typography
      className="mt-1 text-sm">
      {warning}
    </Typography>
  );
};

const ErrorMessage: React.FC<{error: string}> = ({error}) => {
  return (
    <Typography
      className="mt-1 text-sm">
      {error}
    </Typography>
  );
};

const Instructions: React.FC<{instructions: string}> = ({instructions}) => {
  return (
    <Typography
      className="mt-4 text-sm font-normal">
      {instructions}
    </Typography>
  );
};



export const LabeledFormTextField: React.FC<{
  name: string;
  textFieldProps: TextFieldProps;
  icon?: IconName;
  warning?: string;
  error?: string;
  instructions?: string;
}> = ({name, textFieldProps, icon, warning, error, instructions}) => {
  return <Box sx={{
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  }}>
  <FieldName name={name} />
  <TextField {...textFieldProps} />
  {error && <ErrorMessage error={error} />}
  {warning && <WarningMessage warning={warning} />}
  {instructions && <Instructions instructions={instructions} />}
</Box>
}
