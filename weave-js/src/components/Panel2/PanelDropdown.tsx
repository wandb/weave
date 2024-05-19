import {IconChevronDown} from '@wandb/weave/components/Icon';
import {
  constNodeUnsafe,
  constNone,
  constString,
  isList,
  NodeOrVoidNode,
  opUnique,
  voidNode,
} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';
import styled from 'styled-components';

import {useMutation, useNodeValue} from '../../react';
import {
  ConfigFieldModifiedDropdown,
  ConfigFieldWrapper,
  ConfigOption,
  ConfigSection,
  ExpressionConfigField,
} from './ConfigPanel';
import * as Panel2 from './panel';
import {useUpdateConfig2} from './PanelComp';

const inputType = {
  type: 'union' as const,
  members: [
    'none' as const,
    'string' as const,
    {
      type: 'list' as const,
      objectType: {
        type: 'union' as const,
        members: ['unknown' as const, 'string' as const, 'none' as const],
      },
    },
  ],
};

const StyledDiv = styled.div`
  padding: 0 16px;
  && .ui.search.dropdown > .text {
    cursor: pointer;
  }
`;
export interface PanelDropdownConfig {
  choices: NodeOrVoidNode;
}

type PanelDropdownProps = Panel2.PanelProps<
  typeof inputType,
  PanelDropdownConfig
>;

export const PanelDropdownConfigComponent: React.FC<
  PanelDropdownProps
> = props => {
  const config = props.config!;
  const updateConfig2 = useUpdateConfig2(props);
  const updateChoicesExpr = useCallback(
    (newExpr: NodeOrVoidNode) => {
      updateConfig2(currentConfig => ({...currentConfig, choices: newExpr}));
    },
    [updateConfig2]
  );

  return (
    <ConfigSection label={`Properties`}>
      <ConfigOption label={`choices`}>
        <ExpressionConfigField
          expr={config.choices}
          setExpression={updateChoicesExpr}
        />
      </ConfigOption>
    </ConfigSection>
  );
};

export const PanelDropdown: React.FC<PanelDropdownProps> = props => {
  const config = props.config!;

  const uniqueChoicesNode = useMemo(() => {
    if (config.choices.nodeType === 'void') {
      return voidNode();
    } else {
      return opUnique({arr: config.choices});
    }
  }, [config.choices]);
  const choicesQuery = useNodeValue(uniqueChoicesNode);
  const choices: string[] = useMemo(
    () => choicesQuery.result ?? [],
    [choicesQuery]
  );

  const valueNode = props.input;
  const isMultiple = isList(valueNode.type);

  const valueQuery = useNodeValue(valueNode as any);
  const chosen = useMemo(() => valueQuery.result ?? [], [valueQuery]);
  const setVal = useMutation(valueNode, 'set');
  const options = useMemo(() => {
    return choices.map(c => ({text: c, key: c, value: c}));
  }, [choices]);

  return (
    <StyledDiv>
      <ConfigFieldWrapper withIcon>
        <ConfigFieldModifiedDropdown
          value={chosen}
          onChange={(e, {value}) => {
            if (isMultiple) {
              setVal({val: constNodeUnsafe(config.choices.type, value)});
            } else if (value != null) {
              setVal({val: constString(value as string)});
            } else {
              setVal({val: constNone()});
            }
          }}
          options={options}
          multiple={isMultiple}
          floating
          icon={<IconChevronDown width={18} />}
        />
      </ConfigFieldWrapper>
    </StyledDiv>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  initialize: () => ({choices: voidNode()}),
  id: 'Dropdown',
  ConfigComponent: PanelDropdownConfigComponent,
  Component: PanelDropdown,
  inputType,
};
