/**
 * Contains common components and utilities for building config panels.
 * I expect this file to mature and eventually become a general-purpose
 * Weave graph editor.
 */

import React from 'react';
import * as _ from 'lodash';
import {ThemeProvider} from 'styled-components';

import * as S from './styles';

import * as ExpressionEditor from '../ExpressionEditor';
import * as QueryEditorStyles from '../ExpressionEditor.styles';
import ModifiedDropdown from '@wandb/common/components/elements/ModifiedDropdown';
import NumberInput from '@wandb/common/components/elements/NumberInput';

export const ConfigOption: React.FC<
  {
    label: string;
  } & {[key: string]: any}
> = props => {
  return (
    <S.ConfigOption {..._.omit(props, ['label', 'children'])}>
      <S.ConfigOptionLabel>{props.label}</S.ConfigOptionLabel>
      <S.ConfigOptionField>{props.children}</S.ConfigOptionField>
    </S.ConfigOption>
  );
};

export const ModifiedDropdownConfigField: React.FC<
  React.ComponentProps<typeof ModifiedDropdown>
> = props => {
  return (
    <ModifiedDropdown style={{flex: '1 1 auto', width: '100%'}} {...props} />
  );
};

export const NumberInputConfigField: React.FC<
  React.ComponentProps<typeof NumberInput>
> = props => {
  return (
    <NumberInput
      containerStyle={{flex: '1 1 auto', width: '100%'}}
      inputStyle={{width: '100%'}}
      {...props}
    />
  );
};

export const ExpressionConfigField: React.FC<
  React.ComponentProps<typeof ExpressionEditor.ExpressionEditor>
> = props => {
  return (
    <div style={{flex: '1 1 auto', width: '100%'}}>
      <ThemeProvider theme={QueryEditorStyles.themes.light}>
        <ExpressionEditor.ExpressionEditor {...props} />
      </ThemeProvider>
    </div>
  );
};
