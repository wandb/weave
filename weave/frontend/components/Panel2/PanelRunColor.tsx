import React from 'react';
import * as Panel2 from './panel';

import {Icon} from 'semantic-ui-react';
import {useNodeValue} from '@wandb/common/cgreact';
import {usePanelContext} from './PanelContext';

import * as Op from '@wandb/cg/browser/ops';
import {Panel2Loader} from './PanelComp';
const inputType = 'run' as const;
type PanelRunColorProps = Panel2.PanelProps<typeof inputType>;

const PanelRunColor: React.FC<PanelRunColorProps> = props => {
  const {frame} = usePanelContext();
  const colorNode = Op.opPick({
    obj: frame.runColors,
    key: Op.opRunId({
      run: props.input,
    }),
  });
  const colorNodeValue = useNodeValue(colorNode);
  if (colorNodeValue.loading) {
    return <Panel2Loader />;
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        textAlign: 'center',
        display: 'flex',
        alignContent: 'center',
        justifyContent: 'center',
        alignItems: 'center',
      }}>
      <Icon
        style={{
          opacity: 1,
          color: colorNodeValue.result,
          height: '1.5em',
          margin: 0,
          padding: 0,
        }}
        name="circle"
      />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'run-color',
  Component: PanelRunColor,
  inputType,
};
