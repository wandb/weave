import React from 'react';
import * as globals from '@wandb/common/css/globals.styles';
import {useMemo, useState} from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {callOp} from '@wandb/cg/browser/hl';
import {voidNode} from '@wandb/cg/browser/graph';
import {constString, constNumber} from '@wandb/cg/browser/ops';
import {Input} from '@material-ui/core';
import styled from 'styled-components';
// import {Panel2Loader} from './PanelComp.styles';

const inputType = {
  type: 'gpt3-fine-tune-type' as const,
};

interface PanelGpt3ModelConfig {
  inputString: string;
}
type PanelGpt3ModelProps = Panel2.PanelProps<
  typeof inputType,
  PanelGpt3ModelConfig
>;

const KeyValTable = styled.div``;
const KeyValTableRow = styled.div`
  display: flex;
  align-items: flex-start;
`;
const KeyValTableKey = styled.div`
  color: ${globals.gray500};
  width: 100px;
`;
const KeyValTableVal = styled.div`
  flex-grow: 1;
`;

export const PanelGpt3Model: React.FC<PanelGpt3ModelProps> = props => {
  const [inputValue, setInputValue] = useState(props.config?.inputString ?? '');
  const queryNode = useMemo(
    () =>
      props.config?.inputString == null
        ? voidNode()
        : callOp('pick', {
            obj: callOp('index', {
              arr: callOp('pick', {
                obj: callOp('gpt3model-complete', {
                  self: callOp('gpt3finetune-model', {self: props.input}),
                  prompt: constString(props.config?.inputString),
                }),
                key: constString('choices'),
              }),
              index: constNumber(0),
            }),
            key: constString('text'),
          }),
    [props.config, props.input]
  );

  const nodeValueQuery = CGReact.useNodeValue(queryNode as any);
  // TODO: commented out to get rid of flashing
  // if (nodeValueQuery.loading) {
  //   return <Panel2Loader />;
  // }
  return (
    <KeyValTable>
      <KeyValTableRow style={{display: 'flex', alignItems: 'center'}}>
        <KeyValTableKey style={{marginBottom: 6, marginRight: 6}}>
          Prompt
        </KeyValTableKey>
        <KeyValTableVal>
          <Input
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') {
                props.updateConfig({inputString: inputValue});
              }
            }}
          />
        </KeyValTableVal>
      </KeyValTableRow>
      <KeyValTableRow style={{display: 'flex', alignItems: 'center'}}>
        <KeyValTableKey style={{marginTop: 18, marginBottom: 6}}>
          Completion
        </KeyValTableKey>
        <KeyValTableVal>
          {nodeValueQuery.loading ? 'loading...' : nodeValueQuery.result}
        </KeyValTableVal>
      </KeyValTableRow>
    </KeyValTable>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'openai-gpt3-finetune-result',
  Component: PanelGpt3Model,
  inputType,
};
