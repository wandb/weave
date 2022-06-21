import * as _ from 'lodash';
import React from 'react';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import {PanelContextProvider, usePanelContext} from '../Panel2/PanelContext';
import {getPanelStacksForType} from './availablePanels';
import {constString, constNumber} from '@wandb/cg/browser/ops';
import {dereferenceVariables, callOp} from '@wandb/cg/browser/hl';

const inputType = 'invalid';

type PanelContainerProps = Panel2.PanelProps<typeof inputType, any>;

export const PanelContainer: React.FC<PanelContainerProps> = props => {
  const pc = usePanelContext();
  const variables = _.mapValues(props.config.variables, (v, k) =>
    callOp('pick', {
      obj: callOp('panelContainerConfig-variables', {
        self: callOp('containerpanel-config', {self: pc.frame.config}),
      }),
      key: constString(k),
    })
  );
  const panels: JSX.Element[] = [];
  for (let i = 0; i < props.config.panels.length; i++) {
    const panel = props.config.panels[i];
    const panelType = 'number'; // hardcode because its coming as {type: number}
    const {handler} = getPanelStacksForType(panelType, panel.id);
    const newFrame = {
      config: callOp('index', {
        obj: callOp('panelContainerConfig-panels', {
          self: callOp('containerpanel-config', {self: pc.frame.config}),
        }),
        key: constNumber(i),
      }),
    };
    if (handler != null) {
      panels.push(
        <PanelContextProvider newVars={newFrame as any}>
          <PanelComp2
            key={i}
            input={dereferenceVariables(panel.input_node, variables).node}
            inputType={'none'}
            loading={false}
            panelSpec={handler}
            configMode={false}
            context={props.context}
            config={panel.config}
            updateConfig={newConfig => console.log('Panel update config')}
            updateContext={props.updateContext}
            noPanelControls
          />
        </PanelContextProvider>
      );
    } else {
      panels.push(<div>INVALID</div>);
    }
  }
  return (
    <div style={{overflow: 'auto'}}>
      <PanelContextProvider newVars={variables as any}>
        {panels}
      </PanelContextProvider>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'container',
  Component: PanelContainer,
  inputType,
};
