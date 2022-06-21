import React from 'react';
import {useState, useCallback} from 'react';
import * as Panel2 from './panel';
import * as CGReact from '@wandb/common/cgreact';
import {Panel2Loader} from './PanelComp';
import {PanelComp2} from './PanelComp';
import {PanelSpecs} from './PanelRegistry';
import {PanelContextProvider} from './PanelContext';

const inputType = {type: 'panel' as const};
type PanelPanelProps = Panel2.PanelProps<typeof inputType, any>;

export const PanelPanel: React.FC<PanelPanelProps> = props => {
  const panelNode = CGReact.useNodeValue(props.input);
  const [config, setConfig] = useState();

  const panelId = (panelNode.result as any)?.id;
  const defaultConfig = (panelNode.result as any)?.config;
  const inputNode = (panelNode.result as any)?.input;

  const panelConfig = config ?? defaultConfig;
  const updateConfig = useCallback(
    (newConfig: any) => {
      setConfig({...panelConfig, ...newConfig});
    },
    [panelConfig]
  );

  if (panelNode.loading) {
    return <Panel2Loader />;
  }
  if (panelNode.result == null) {
    return <div>-</div>;
  }

  const panelSpec = PanelSpecs().filter(spec => spec.id === panelId)[0];
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
      <PanelContextProvider newVars={{config: props.input}}>
        <PanelComp2
          input={inputNode}
          inputType={'none'}
          loading={false}
          panelSpec={panelSpec}
          configMode={false}
          context={props.context}
          config={panelConfig}
          updateConfig={updateConfig}
          updateContext={props.updateContext}
          noPanelControls
        />
      </PanelContextProvider>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'panel',
  Component: PanelPanel,
  inputType,
};
