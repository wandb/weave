import {displayValueNoBarChart} from '@wandb/weave/common/util/runhelpers';
import React from 'react';

import * as CGReact from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';

const inputType = {
  type: 'union' as const,
  members: ['none' as const, 'number' as const],
};
type PanelNumberProps = Panel2.PanelProps<typeof inputType>;
type PanelNumberExtraProps = {
  textAlign?: 'left' | 'right' | 'center' | 'justify' | 'initial' | 'inherit';
};

export const PanelNumber: React.FC<
  PanelNumberProps & PanelNumberExtraProps
> = props => {
  const nodeValueQuery = CGReact.useNodeValue(props.input);
  if (nodeValueQuery.loading) {
    return <Panel2Loader />;
  }
  const textAlign = props.textAlign ?? 'center';

  return (
    <div
      data-test-weave-id="number"
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'auto',
        margin: 'auto',
        textAlign,
        wordBreak: 'normal',
        display: 'flex',
        flexDirection: 'column',
        alignContent: 'space-around',
        justifyContent: 'space-around',
        alignItems: textAlign === 'center' ? 'center' : 'normal',
      }}>
      {nodeValueQuery.result == null
        ? '-'
        : displayValueNoBarChart(nodeValueQuery.result)}
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'number',
  Component: PanelNumber,
  inputType,
};
