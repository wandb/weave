import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import {useGatedValue} from '@wandb/common/state/hooks';

const inputType = 'any';
type PanelAnyObjProps = Panel2.PanelProps<typeof inputType>;

export const PanelAnyObj: React.FC<PanelAnyObjProps> = props => {
  let nodeValueQuery = CGReact.useNodeValue(props.input);
  nodeValueQuery = useGatedValue(nodeValueQuery, () => !nodeValueQuery.loading);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  return (
    <pre style={{fontSize: 10, lineHeight: 1.3}}>
      {JSON.stringify(nodeValueQuery.result, undefined, 2)}
    </pre>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'any-obj',
  Component: PanelAnyObj,
  inputType,
};
