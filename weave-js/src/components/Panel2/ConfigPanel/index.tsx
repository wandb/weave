/**
 * Contains common components and utilities for building config panels.
 * I expect this file to mature and eventually become a general-purpose
 * Weave graph editor.
 */

import ModifiedDropdown from '@wandb/weave/common/components/elements/ModifiedDropdown';
import NumberInput from '@wandb/weave/common/components/elements/NumberInput';
import {TextInput} from '@wandb/weave/common/components/elements/TextInput';
import * as _ from 'lodash';
import React, {useMemo} from 'react';
import {ThemeProvider} from 'styled-components';

import {useWeaveDashUiEnable} from '../../../context';
import {WeaveExpression} from '../../../panel/WeaveExpression';
import {themes} from '../Editor.styles';
import * as S from './styles';

export const ConfigOption: React.FC<
  {
    label: string;
    // component to append after the the config component, on the same line, such as
    // "add new y" buttons or "delete option" buttons. see panelplot config y for
    // an example.
    postfixComponent?: React.ReactElement;
  } & {[key: string]: any}
> = props => {
  return (
    <S.ConfigOption
      {..._.omit(props, ['label', 'children', 'postfixComponent'])}>
      {props.label !== '' ? (
        <S.ConfigOptionLabel>{props.label}</S.ConfigOptionLabel>
      ) : (
        <></>
      )}
      <S.ConfigOptionField>{props.children}</S.ConfigOptionField>
      {props.postfixComponent}
    </S.ConfigOption>
  );
};

export const ModifiedDropdownConfigField: React.FC<
  React.ComponentProps<typeof ModifiedDropdown>
> = props => {
  const dashEnabled = useWeaveDashUiEnable();
  const dropdownProps = useMemo(() => {
    const p = {...props};
    if (dashEnabled) {
      delete p.selection;
      p.compact = true;
    }
    return p;
  }, [dashEnabled, props]);
  return (
    <ModifiedDropdown
      style={{flex: '1 1 auto', width: '100%'}}
      {...dropdownProps}
    />
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
  React.ComponentProps<typeof WeaveExpression>
> = props => {
  const dashEnabled = useWeaveDashUiEnable();
  return (
    <div style={{flex: '1 1 auto', width: '100%'}}>
      <ThemeProvider theme={themes.light}>
        <WeaveExpression
          noBox={true}
          setExpression={props.setExpression}
          expr={props.expr}
          liveUpdate={!dashEnabled}
        />
      </ThemeProvider>
    </div>
  );
};

export const TextInputConfigField: React.FC<
  React.ComponentProps<typeof TextInput>
> = props => {
  return (
    <div style={{flex: '1 1 auto', width: '100%'}}>
      <TextInput {...props} />
    </div>
  );
};
