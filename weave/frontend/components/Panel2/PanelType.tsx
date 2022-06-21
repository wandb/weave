import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import * as Types from '@wandb/cg/browser/model/types';

const inputType = 'type' as const;
type PanelTypeProps = Panel2.PanelProps<typeof inputType>;

export const PanelType: React.FC<PanelTypeProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <div>-</div>;
  }
  return <div>{Types.toString(nodeValueQuery.result)}</div>;
};

export const Spec: Panel2.PanelSpec = {
  id: 'type',
  Component: PanelType,
  inputType,
};
