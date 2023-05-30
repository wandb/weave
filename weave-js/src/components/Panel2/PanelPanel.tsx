import {useTraceUpdate} from '@wandb/weave/common/util/hooks';
import {constNodeUnsafe, Node, voidNode} from '@wandb/weave/core';
import produce from 'immer';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {Button, Icon} from 'semantic-ui-react';

import {useWeaveContext} from '../../context';
import * as CGReact from '../../react';
import {useMutation} from '../../react';
import {consoleLog} from '../../util';
import {Outline} from '../Sidebar/Outline';
import {
  ChildPanel,
  ChildPanelConfig,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
  getFullChildPanel,
} from './ChildPanel';
import * as Panel2 from './panel';
import {Panel2Loader} from './PanelComp';
import {PanelContextProvider} from './PanelContext';
import {fixChildData, toWeaveType} from './PanelGroup';
import {useSelectedPath, useSetInspectingPanel} from './PanelInteractContext';
import {useSetPanelRenderedConfig} from './PanelRenderedConfigContext';
import * as PanelTree from './panelTree';

const inputType = {type: 'Panel' as const};
type PanelPanelProps = Panel2.PanelProps<
  typeof inputType,
  ChildPanelFullConfig
>;

const usePanelPanelCommon = (props: PanelPanelProps) => {
  const weave = useWeaveContext();
  const {updateConfig2, updateInput} = props;
  if (updateConfig2 == null) {
    throw new Error('updateConfig2 is required');
  }
  const panelQuery = CGReact.useNodeValue(props.input);
  const selectedPanel = useSelectedPath();
  const setSelectedPanel = useSetInspectingPanel();
  const panelConfig = props.config;
  const initialLoading = panelConfig == null;

  const setPanelConfig = updateConfig2;

  useEffect(() => {
    if (initialLoading && !panelQuery.loading) {
      setPanelConfig(() => getFullChildPanel(panelQuery.result));
      return;
    }
  }, [initialLoading, panelQuery.loading, panelQuery.result, setPanelConfig]);
  useTraceUpdate('panelQuery', {
    loading: panelQuery.loading,
    result: panelQuery.result,
  });

  useSetPanelRenderedConfig(panelConfig);

  const handleRootUpdate = useCallback(
    (newVal: Node) => {
      consoleLog('PANEL PANEL HANDLE ROOT UPDATE', newVal);
      if (
        weave.expToString(props.input) !== weave.expToString(newVal) &&
        updateInput
      ) {
        updateInput(newVal as any);
      }
    },
    [props.input, updateInput, weave]
  );

  const setServerPanelConfig = useMutation(
    props.input,
    'set',
    handleRootUpdate
  );

  const panelUpdateConfig = useCallback(
    (newConfig: any) => {
      consoleLog('PANEL PANEL CONFIG UPDATE', newConfig);
      consoleLog('PANEL PANEL CONFIG UPDATE TYPE', toWeaveType(newConfig));
      setPanelConfig(origConfig => ({...origConfig, ...newConfig}));
      // Uncomment to enable panel state saving
      // Need to do fixChildData because the panel config is not fully hydrated.
      const fixedConfig = fixChildData(getFullChildPanel(newConfig), weave);
      setServerPanelConfig({
        val: constNodeUnsafe(toWeaveType(fixedConfig), fixedConfig),
      });
    },
    [setPanelConfig, setServerPanelConfig, weave]
  );
  const panelUpdateConfig2 = useCallback(
    (change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig) => {
      setPanelConfig((currentConfig: ChildPanelFullConfig) => {
        if (currentConfig == null) {
          throw new Error('Cannot update config before it is loaded');
        }
        const configChanges = change(currentConfig);
        const newConfig = produce(currentConfig, (draft: any) => {
          for (const key of Object.keys(configChanges)) {
            (draft as any)[key] = (configChanges as any)[key];
          }
        });
        consoleLog('PANEL PANEL CONFIG UPDATE2', newConfig);
        // Need to do fixChildData because the panel config is not fully hydrated.
        const fixedConfig = fixChildData(getFullChildPanel(newConfig), weave);
        setServerPanelConfig({
          val: constNodeUnsafe(toWeaveType(fixedConfig), fixedConfig),
        });
        return newConfig;
      });
    },
    [setPanelConfig, setServerPanelConfig, weave]
  );
  consoleLog('PANEL PANEL RENDER CONFIG', panelConfig);

  return {
    loading: initialLoading,
    panelConfig,
    selectedPanel,
    setSelectedPanel,
    panelUpdateConfig,
    panelUpdateConfig2,
  };
};

export const PanelPanelConfig: React.FC<PanelPanelProps> = props => {
  const {
    loading,
    panelConfig,
    selectedPanel,
    setSelectedPanel,
    panelUpdateConfig,
    panelUpdateConfig2,
  } = usePanelPanelCommon(props);
  const selected = useMemo(
    () =>
      selectedPanel.length === 1
        ? ['root']
        : selectedPanel.filter(s => s !== ''),
    [selectedPanel]
  );
  const [outlineExpanded, setOutlineExpanded] = useState(true);
  const [inspectorExpanded, setInspectorExpanded] = useState(true);

  const handleEmptyDashboard = useCallback(() => {
    panelUpdateConfig2(oldConfig => {
      const res = PanelTree.ensureDashboard(voidNode());
      consoleLog('EMPTY STATE', res);
      return res;
    });
  }, [panelUpdateConfig2]);

  if (loading) {
    return <Panel2Loader />;
  }
  if (panelConfig == null) {
    throw new Error('Panel config is null after loading');
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'hidden',
        // wordBreak: 'normal',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <div
        style={{
          display: 'flex',
          paddingTop: 4,
          marginBottom: 4,
          paddingLeft: 10,
          borderTop: '1px solid #ccc',
        }}>
        <Button size="mini" onClick={handleEmptyDashboard}>
          Reset Dashboard
        </Button>
      </div>
      <div
        style={{
          paddingLeft: 2,
          paddingTop: 4,
          paddingBottom: 4,
          borderTop: '1px solid #ccc',
          display: 'flex',
          alignItems: 'center',
          cursor: 'pointer',
        }}
        onClick={() => setOutlineExpanded(expanded => !expanded)}>
        <Icon
          size="mini"
          name={outlineExpanded ? 'chevron down' : 'chevron right'}
        />
        <span style={{fontWeight: 'bold'}}>Outline</span>
      </div>
      {outlineExpanded && (
        <div
          style={{
            flex: '0 0 auto',
            overflowX: 'hidden',
            maxHeight: 350,
            overflowY: 'auto',
            padding: '0 8px',
          }}>
          <Outline
            config={panelConfig}
            updateConfig={panelUpdateConfig}
            updateConfig2={panelUpdateConfig2}
            setSelected={setSelectedPanel}
            selected={selectedPanel}
          />
        </div>
      )}
      <div
        style={{
          paddingLeft: 2,
          paddingTop: 4,
          paddingBottom: 4,
          borderTop: '1px solid #ccc',
          display: 'flex',
          alignItems: 'center',
          cursor: 'pointer',
        }}
        onClick={() => setInspectorExpanded(expanded => !expanded)}>
        <Icon
          size="mini"
          name={inspectorExpanded ? 'chevron down' : 'chevron right'}
        />
        {selected.map((s, i) => (
          <span key={i}>
            <span style={{fontWeight: 'bold'}}>{s}</span>
            {i < selected.length - 1 ? <span> | </span> : null}
          </span>
        ))}
      </div>
      <div style={{overflowY: 'auto', padding: '4px', flexGrow: 1}}>
        {/* height: 99% gets rid of scrollbar content is small enough. Not sure why
        this is needed */}
        <div style={{height: '99%'}}>
          {inspectorExpanded && (
            <PanelContextProvider newVars={{}} selectedPath={selectedPanel}>
              <ChildPanelConfigComp
                config={panelConfig}
                updateConfig={panelUpdateConfig}
                updateConfig2={panelUpdateConfig2}
              />
            </PanelContextProvider>
          )}
        </div>
      </div>
    </div>
  );
};

export const PanelPanel: React.FC<PanelPanelProps> = props => {
  const {loading, panelConfig, panelUpdateConfig, panelUpdateConfig2} =
    usePanelPanelCommon(props);

  if (loading) {
    return <Panel2Loader />;
  }
  if (panelConfig == null) {
    throw new Error('Panel config is null after loading');
  }

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowX: 'hidden',
        overflowY: 'hidden',
        margin: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignContent: 'space-around',
        justifyContent: 'space-around',
      }}>
      <ChildPanel
        config={panelConfig}
        updateConfig={panelUpdateConfig}
        updateConfig2={panelUpdateConfig2}
      />
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'panel',
  ConfigComponent: PanelPanelConfig,
  Component: PanelPanel,
  inputType,
};
