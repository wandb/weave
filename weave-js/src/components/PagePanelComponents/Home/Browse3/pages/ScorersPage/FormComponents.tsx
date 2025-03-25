import {Box, InputLabel} from '@material-ui/core';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React from 'react';

import {MOON_500} from '../../../../../../common/css/color.styles';

export const GAP_BETWEEN_ITEMS_PX = 16;
export const GAP_BETWEEN_LABEL_AND_FIELD_PX = 10;
export const GAP_BETWEEN_DESCRIPTION_AND_FIELD_PX = 8;

type AutocompleteWithLabelType<Option = any> = (
  props: {
    label?: string;
    description?: string;
    style?: React.CSSProperties;
  } & React.ComponentProps<typeof Select<Option>>
) => React.ReactElement;

export const AutocompleteWithLabel: AutocompleteWithLabelType = ({
  label,
  description,
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
      <>
        <InputLabel
          style={{
            marginBottom: description
              ? '0px'
              : GAP_BETWEEN_LABEL_AND_FIELD_PX + 'px',
          }}>
          {label}
        </InputLabel>
        {description && (
          <div
            style={{
              color: MOON_500,
              fontSize: '0.875rem',
              marginBottom: GAP_BETWEEN_DESCRIPTION_AND_FIELD_PX + 'px',
            }}>
            {description}
          </div>
        )}
      </>
    )}
    <Select {...props} />
  </Box>
);

type TextFieldWithLabelType = (
  props: {
    label?: string;
    description?: string;
    style?: React.CSSProperties;
    isOptional?: boolean;
  } & React.ComponentProps<typeof TextField>
) => React.ReactElement;

export const TextFieldWithLabel: TextFieldWithLabelType = ({
  label,
  description,
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
      <>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            marginBottom: description
              ? '0px'
              : GAP_BETWEEN_LABEL_AND_FIELD_PX + 'px',
          }}>
          <InputLabel>{label}</InputLabel>
          {isOptional && (
            <span
              style={{
                color: MOON_500,
                marginLeft: '4px',
                alignSelf: 'center',
                fontSize: '14px',
              }}>
              (optional)
            </span>
          )}
        </div>
        {description && (
          <div
            style={{
              color: MOON_500,
              fontSize: '0.875rem',
              marginBottom: GAP_BETWEEN_DESCRIPTION_AND_FIELD_PX + 'px',
            }}>
            {description}
          </div>
        )}
      </>
    )}
    <TextField {...props} />
  </Box>
);
