import {Box, InputLabel} from '@material-ui/core';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React from 'react';

export const GAP_BETWEEN_ITEMS_PX = 16;
export const GAP_BETWEEN_LABEL_AND_FIELD_PX = 10;

type AutocompleteWithLabelType<Option = any> = (
  props: {
    label?: string;
    style?: React.CSSProperties;
  } & React.ComponentProps<typeof Select<Option>>
) => React.ReactElement;

export const AutocompleteWithLabel: AutocompleteWithLabelType = ({
  label,
  style,
  ...props
}) => (
  <Box
    style={{
      marginBottom: GAP_BETWEEN_ITEMS_PX + 'px',
      padding: '0px 2px',
      ...style,
    }}>
    {label && (
      <InputLabel style={{marginBottom: GAP_BETWEEN_LABEL_AND_FIELD_PX + 'px'}}>
        {label}
      </InputLabel>
    )}
    <Select {...props} />
  </Box>
);

type TextFieldWithLabelType = (
  props: {
    label?: string;
    style?: React.CSSProperties;
    isOptional?: boolean;
  } & React.ComponentProps<typeof TextField>
) => React.ReactElement;

export const TextFieldWithLabel: TextFieldWithLabelType = ({
  label,
  style,
  isOptional,
  ...props
}) => (
  <Box
    style={{
      marginBottom: GAP_BETWEEN_ITEMS_PX + 'px',
      padding: '0px 2px',
      ...style,
    }}>
    {label && (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          marginBottom: GAP_BETWEEN_LABEL_AND_FIELD_PX + 'px',
        }}>
        <InputLabel>{label}</InputLabel>
        {isOptional && (
          <span
            style={{
              color: 'gray',
              marginLeft: '4px',
              alignSelf: 'center',
              fontSize: '14px',
            }}>
            (optional)
          </span>
        )}
      </div>
    )}
    <TextField {...props} />
  </Box>
);
