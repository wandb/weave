import {isVoidNode, opPick, opRunId} from '@wandb/weave/core';
import React from 'react';
import {Icon} from 'semantic-ui-react';

import {useNodeValue} from '../../react';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {usePanelContext} from './PanelContext';

const inputType = 'run' as const;
type PanelRunColorProps = Panel2.PanelProps<typeof inputType>;

const PanelRunColor: React.FC<PanelRunColorProps> = props => {
  const {frame} = usePanelContext();
  if (frame.runColors == null || isVoidNode(frame.runColors)) {
    throw new Error(
      `PanelRunColor received unusable runColors variable in frame`
    );
  }
  const colorNode = opPick({
    obj: frame.runColors,
    key: opRunId({
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
  hidden: true,
  Component: PanelRunColor,
  inputType,
};
