import React from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import {displayValueNoBarChart} from '@wandb/common/util/runhelpers';

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'number' as const],
};
type PanelNumberProps = Panel2.PanelProps<typeof inputType>;

export const PanelNumber: React.FC<PanelNumberProps> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  if (nodeValueQuery.result == null) {
    return <div>-</div>;
  }
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
        margin: 'auto',
        textAlign: 'center',
        wordBreak: 'normal',
        display: 'flex',
        flexDirection: 'column',
        alignContent: 'space-around',
        justifyContent: 'space-around',
        alignItems: 'center',
      }}>
      {displayValueNoBarChart(nodeValueQuery.result)}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'number',
  Component: PanelNumber,
  inputType,
};
