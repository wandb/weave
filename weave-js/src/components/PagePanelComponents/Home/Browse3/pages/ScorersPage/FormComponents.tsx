import {Box, InputLabel} from '@material-ui/core';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React from 'react';

type AutocompleteWithLabelType<Option = any> = (
  props: {
    label: string;
  } & React.ComponentProps<typeof Select<Option>>
) => React.ReactElement;

export const AutocompleteWithLabel: AutocompleteWithLabelType = ({
  label,
  ...props
}) => (
  <Box style={{marginBottom: '10px', padding: '0px 2px'}}>
    <InputLabel style={{marginBottom: '10px', fontSize: '14px'}}>
      {label}
    </InputLabel>
    <Select {...props} />
  </Box>
);

type TextFieldWithLabelType = (
  props: {
    label?: string;
  } & React.ComponentProps<typeof TextField>
) => React.ReactElement;

export const TextFieldWithLabel: TextFieldWithLabelType = ({
  label,
  ...props
}) => (
  <Box style={{marginBottom: '10px', padding: '0px 2px'}}>
    {label && (
      <InputLabel style={{marginBottom: '10px', fontSize: '14px'}}>
        {label}
      </InputLabel>
    )}
    <TextField {...props} />
  </Box>
);
