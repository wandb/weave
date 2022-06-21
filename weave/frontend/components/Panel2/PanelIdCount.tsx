import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import * as Op from '@wandb/cg/browser/ops';

const inputType = {
  type: 'list' as const,
  objectType: {
    type: 'union' as const,
    members: ['none' as const, 'id' as const],
  },
};

type PanelIdCountProps = Panel2.PanelProps<typeof inputType>;

const PanelIdCount: React.FC<PanelIdCountProps> = props => {
  const counted = Op.opCount({arr: props.input});
  const nodeValue = CGReact.useNodeValue(counted);
  if (nodeValue.loading) {
    return <div>-</div>;
  }
  return <div>{nodeValue.result} ids</div>;
};

export const Spec: Panel2.PanelSpec = {
  id: 'id-count',
  Component: PanelIdCount,
  inputType,
};
