import {
  constNodeUnsafe,
  isNullable,
  listObjectType,
  NodeOrVoidNode,
  opUnique,
  voidNode,
} from '@wandb/weave/core';
import React, {useCallback, useMemo} from 'react';
import {Checkbox} from 'semantic-ui-react';

import {useMutation, useNodeValue} from '../../react';
import {
  ConfigOption,
  ConfigSection,
  ExpressionConfigField,
} from './ConfigPanel';
import * as Panel2 from './panel';
import {useUpdateConfig2} from './PanelComp';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['unknown' as const, 'string' as const, 'none' as const],
  },
};

export interface PanelSelectEditorConfig {
  choices: NodeOrVoidNode;
}

type PanelSelectEditorProps = Panel2.PanelProps<
  typeof inputType,
  PanelSelectEditorConfig
>;

export const PanelSelectEditorConfigComponent: React.FC<
  PanelSelectEditorProps
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

export const PanelSelectEditor: React.FC<PanelSelectEditorProps> = props => {
  const config = props.config!;

  const uniqueChoicesNode = useMemo(() => {
    if (config.choices.nodeType === 'void') {
      return voidNode();
    } else {
      return opUnique({arr: config.choices});
    }
  }, [config.choices]);
  const choicesQuery = useNodeValue(uniqueChoicesNode);
  const choices = useMemo(() => choicesQuery.result ?? [], [choicesQuery]);
  const valueNode = props.input;
  const valueQuery = useNodeValue(valueNode);
  const chosen = useMemo(() => valueQuery.result ?? [], [valueQuery]);
  const setVal = useMutation(valueNode, 'set');
  // const setVal = useMutation(valueNode, 'set');
  const toggleRow = useCallback(
    (val: string) => {
      if (chosen.includes(val)) {
        let newVal = chosen.filter(v => v !== val);
        // TODO: This is a major hack, backend expects a union here
        // But its been removed by the time we have it.
        if (isNullable(listObjectType(config.choices.type))) {
          newVal = newVal.map(v => ({_val: v, _union_id: 1})) as any;
        }
        setVal({val: constNodeUnsafe(config.choices.type, newVal)});
        return;
      } else {
        let newVal = [...chosen, val];
        // TODO: This is a major hack, backend expects a union here
        // But its been removed by the time we have it.
        if (isNullable(listObjectType(config.choices.type))) {
          newVal = newVal.map(v => ({_val: v, _union_id: 1})) as any;
        }
        setVal({val: constNodeUnsafe(config.choices.type, newVal)});
        return;
      }
    },
    [chosen, config.choices.type, setVal]
  );

  // if (valueQuery.loading) {
  //   return <Panel2Loader />;
  // }

  return (
    <div style={{paddingLeft: 16}}>
      {choices.map((item: string, i: number) => (
        <div
          key={i}
          style={{
            display: 'flex',
            alignItems: 'center',
          }}>
          <Checkbox
            checked={chosen.includes(item)}
            onChange={e => toggleRow(item)}
            style={{marginRight: 8}}
          />
          {item}
        </div>
      ))}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  hidden: true,
  initialize: () => ({choices: voidNode()}),
  id: 'SelectEditor',
  ConfigComponent: PanelSelectEditorConfigComponent,
  Component: PanelSelectEditor,
  inputType,
};
