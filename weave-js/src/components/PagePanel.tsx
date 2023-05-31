import * as globals from '@wandb/weave/common/css/globals.styles';
import Loader from '@wandb/weave/common/components/WandbLoader';
import getConfig from '../config';
import {Node, NodeOrVoidNode, voidNode} from '@wandb/weave/core';
import produce from 'immer';
import moment from 'moment';
import React from 'react';
import {useCallback, useEffect, useState} from 'react';
import {Button, Icon, Input} from 'semantic-ui-react';
import {ThemeProvider} from 'styled-components';

import {useWeaveContext} from '../context';
import {consoleLog} from '../util';
import {useWeaveAutomation} from './automation';
import {PersistenceManager} from './PagePanelComponents/PersistenceManager';
import {
  CHILD_PANEL_DEFAULT_CONFIG,
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
} from './Panel2/ChildPanel';
import {themes} from './Panel2/Editor.styles';
import {dummyProps, useConfig} from './Panel2/panel';
import * as Styles from './Panel2/PanelExpression/styles';
import {
  PanelInteractContextProvider,
  useEditorIsOpen,
} from './Panel2/PanelInteractContext';
import {PanelRenderedConfigContextProvider} from './Panel2/PanelRenderedConfigContext';
import {PanelRootBrowser} from './Panel2/PanelRootBrowser/PanelRootBrowser';
import {useNewPanelFromRootQueryCallback} from './Panel2/PanelRootBrowser/util';
import Inspector from './Sidebar/Inspector';
import {useNodeWithServerType} from '../react';
import {inJupyterCell, weaveTypeIsPanel} from './PagePanelComponents/util';

const EditorSidebar: React.FC<{
  config: ChildPanelFullConfig;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  updateConfig2: (change: (oldConfig: any) => any) => void;
}> = props => {
  const editorIsOpen = useEditorIsOpen();

  return (
    <Styles.SidebarWrapper>
      <Inspector collapsed={!editorIsOpen}>
        {editorIsOpen && (
          <ChildPanelConfigComp
            // pathEl={CHILD_NAME}
            config={props.config}
            updateConfig={props.updateConfig}
            updateConfig2={props.updateConfig2}
          />
        )}
      </Inspector>
    </Styles.SidebarWrapper>
  );
};

interface HomeProps {
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  inJupyter: boolean;
}

const Home: React.FC<HomeProps> = props => {
  const now = moment().format('YY_MM_DD_hh_mm_ss');
  const inJupyter = props.inJupyter;
  const defaultName = now;
  const [newName, setNewName] = useState('');
  const weave = useWeaveContext();
  const name = 'dashboard-' + (newName === '' ? defaultName : newName);
  const makeNewDashboard = useNewPanelFromRootQueryCallback();
  const {urlPrefixed} = getConfig();
  const newDashboard = useCallback(() => {
    makeNewDashboard(name, voidNode(), true, newDashExpr => {
      if (inJupyter) {
        const expStr = weave
          .expToString(newDashExpr)
          .replace(/\n+/g, '')
          .replace(/\s+/g, '');
        window.open(
          urlPrefixed(`?exp=${encodeURIComponent(expStr)}`),
          '_blank'
        );
      } else {
        props.updateConfig({
          vars: {},
          input_node: newDashExpr,
          id: '',
          config: undefined,
        });
      }
    });
  }, [inJupyter, makeNewDashboard, name, props, urlPrefixed, weave]);
  const [rootConfig, updateRootConfig] = useConfig();
  const updateInput = useCallback(
    (newInput: Node) => {
      props.updateConfig({
        vars: {},
        input_node: newInput,
        id: '',
        config: undefined,
      });
    },
    [props]
  );
  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
      <div
        style={{
          width: '100%',
          height: '90%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          // marginTop: 16,
          // marginBottom: 16,
        }}>
        <div
          style={{
            width: '90%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexDirection: 'column',
            gap: 16,
          }}>
          <div
            style={{
              display: 'flex',
              flexDirection: 'row',
              // width: 400,
              padding: 16,
              border: '1px solid #eee',
              gap: 16,
              width: '100%',
            }}>
            <div
              style={{
                flexGrow: 1,
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}>
              <div
                style={{width: '100%', display: 'flex', alignItems: 'center'}}
                onKeyUp={e => {
                  if (e.key === 'Enter') {
                    newDashboard();
                  }
                }}>
                <Input
                  placeholder={defaultName}
                  style={{flexGrow: 1}}
                  value={newName}
                  onChange={(e, {value}) => setNewName(value)}
                />
              </div>
              <div
                style={{
                  display: 'flex',
                  flex: 1,
                  width: '100%',
                }}>
                <Button onClick={newDashboard}>New dashboard</Button>
              </div>
            </div>
          </div>
          <div
            style={{
              width: '100%',
              height: '100%',
              padding: 16,
              border: '1px solid #eee',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}>
            {/* <div style={{marginBottom: 32}}>Your Weave Objects</div> */}
            <div style={{flexGrow: 1, overflow: 'auto'}}>
              <PanelRootBrowser
                input={voidNode() as any}
                updateInput={updateInput as any}
                isRoot={true}
                config={rootConfig}
                updateConfig={updateRootConfig}
                context={dummyProps.context}
                updateContext={dummyProps.updateContext}
              />
              {/* <DashboardList loadDashboard={loadDashboard} /> */}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const PagePanel: React.FC = props => {
  const weave = useWeaveContext();
  const urlParams = new URLSearchParams(window.location.search);
  const fullScreen = urlParams.get('fullScreen') != null;
  const expString = urlParams.get('exp');
  const expNode = urlParams.get('expNode');
  const panelId = urlParams.get('panelId') ?? '';
  const automationId = urlParams.get('automationId');
  let panelConfig = urlParams.get('panelConfig') ?? undefined;
  const [loading, setLoading] = useState(true);
  if (panelConfig != null) {
    panelConfig = JSON.parse(panelConfig);
  }
  const inJupyter = inJupyterCell();

  const setUrlExp = useCallback(
    (exp: NodeOrVoidNode) => {
      const newExpStr = weave.expToString(exp);
      if (newExpStr === expString) {
        return;
      }
      const searchParams = new URLSearchParams(window.location.search);
      searchParams.set('exp', newExpStr);
      window.history.replaceState(
        null,
        '',
        `${window.location.pathname}?${searchParams}`
      );
    },
    [expString, weave]
  );

  const [config, setConfig] = useState<ChildPanelFullConfig>(
    CHILD_PANEL_DEFAULT_CONFIG
  );
  const updateConfig = useCallback(
    (newConfig: Partial<ChildPanelFullConfig>) => {
      setConfig(currentConfig => ({...currentConfig, ...newConfig}));
      if (newConfig.input_node != null) {
        setUrlExp(newConfig.input_node);
      }
    },
    [setConfig, setUrlExp]
  );
  const updateConfig2 = useCallback(
    (
      change: (oldConfig: ChildPanelFullConfig) => Partial<ChildPanelFullConfig>
    ) => {
      setConfig(currentConfig => {
        const configChanges = change(currentConfig);
        if (configChanges.input_node != null) {
          setUrlExp(configChanges.input_node);
        }
        const newConfig = produce(currentConfig, draft => {
          for (const key of Object.keys(configChanges)) {
            (draft as any)[key] = (configChanges as any)[key];
          }
        });
        consoleLog(
          'PagePanel config update. Old: ',
          currentConfig,
          ' Changes: ',
          configChanges,
          ' New: ',
          newConfig
        );
        return newConfig;
      });
    },
    [setConfig, setUrlExp]
  );
  const [forceRemount, setForceRemount] = useState(0);

  const updateInputNode = useCallback(
    (newInputNode: NodeOrVoidNode) => {
      updateConfig({input_node: newInputNode});
      setForceRemount(r => r + 1);
    },
    [updateConfig]
  );

  useWeaveAutomation(automationId);

  useEffect(() => {
    consoleLog('PAGE PANEL MOUNT');
    setLoading(true);
    if (expString != null) {
      weave.expression(expString, []).then(res => {
        updateConfig({
          input_node: res.expr as any,
          id: panelId,
          config: panelConfig,
        } as any);
        setLoading(false);
      });
    } else if (expNode != null) {
      updateConfig({
        input_node: JSON.parse(expNode) as any,
        id: panelId,
        config: panelConfig,
      } as any);
      setLoading(false);
    } else {
      updateConfig({
        input_node: voidNode(),
        id: panelId,
        config: panelConfig,
      } as any);
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expString, forceRemount]);

  // Moved here from PanelExpression, not sure if working yet.
  // TODO: play/pause
  // const [weaveIsAutoRefresh, setWeaveIsAutoRefresh] = React.useState(
  const [, /*weaveIsAutoRefresh*/ setWeaveIsAutoRefresh] = React.useState(
    weave.client.isPolling()
  );
  const onPollChangeListener = React.useCallback((isPolling: boolean) => {
    setWeaveIsAutoRefresh(isPolling);
  }, []);
  React.useEffect(() => {
    weave.client.addOnPollingChangeListener(onPollChangeListener);
    return () => {
      weave.client.removeOnPollingChangeListener(onPollChangeListener);
    };
  }, [weave, onPollChangeListener]);

  // const toggleAutoRefresh = React.useCallback(
  //   (val: boolean) => {
  //     weave.client.setPolling(!weaveIsAutoRefresh);
  //   },
  //   [weave, weaveIsAutoRefresh]
  // );

  const goHome = React.useCallback(() => {
    updateConfig({
      vars: {},
      input_node: voidNode(),
      id: '',
      config: undefined,
    });
  }, [updateConfig]);

  const position = fullScreen ? 'fixed' : 'absolute';

  const {urlPrefixed} = getConfig();

  const typedInputNode = useNodeWithServerType(config.input_node);
  const isPanel = weaveTypeIsPanel(
    typedInputNode.result?.type || {type: 'Panel' as any}
  );

  if (loading) {
    return <Loader name="page-panel-loader" />;
  }

  return (
    <ThemeProvider theme={themes.light}>
      <PanelRenderedConfigContextProvider>
        <PanelInteractContextProvider>
          <div
            className="weave-root"
            style={{
              position,
              backgroundColor: '#fff',
              color: globals.TEXT_PRIMARY_COLOR,
              top: 0,
              bottom: 0,
              left: 0,
              right: 0,
            }}>
            {config.input_node.nodeType === 'void' ? (
              <Home updateConfig={updateConfig} inJupyter={inJupyter} />
            ) : (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                }}>
                {!inJupyter && (
                  <PersistenceManager
                    inputNode={config.input_node}
                    updateNode={updateInputNode}
                    goHome={goHome}
                  />
                )}
                <div
                  style={{
                    flex: '1 1 300px',
                    overflow: 'hidden',
                  }}>
                  <ChildPanel
                    editable={inJupyter || !isPanel}
                    prefixHeader={
                      inJupyter ? (
                        <Icon
                          style={{cursor: 'pointer', color: '#555'}}
                          name="home"
                          onClick={goHome}
                        />
                      ) : (
                        <></>
                      )
                    }
                    prefixButtons={
                      <>
                        {/* <Styles.ConfigButton
                          onClick={toggleAutoRefresh}
                          style={{
                            padding: '8px',
                          }}>
                          <Icon
                            name={weaveIsAutoRefresh ? 'pause' : 'play'}
                            style={{margin: 0}}
                          />
                        </Styles.ConfigButton> */}
                        {inJupyter && (
                          <Styles.BarButton
                            onClick={() => {
                              const expStr = weave
                                .expToString(config.input_node)
                                .replace(/\n+/g, '')
                                .replace(/\s+/g, '');
                              window.open(
                                urlPrefixed(
                                  `?exp=${encodeURIComponent(expStr)}`
                                ),
                                '_blank'
                              );
                            }}>
                            <Icon name="external square alternate" />
                          </Styles.BarButton>
                        )}
                      </>
                    }
                    config={config}
                    updateConfig={updateConfig}
                    updateConfig2={updateConfig2}
                  />
                </div>
                {/* <div
                  style={{
                    flex: '0 0 22px',
                    height: '16px',
                    overflow: 'hidden',
                    backgroundColor: '#fff',
                    borderTop: '1px solid #ddd',
                  }}>
                    PLACEHOLDER FOR EXECUTION DETAILS
                  </div> */}
              </div>
            )}
            {/* <ArtifactManager /> */}
          </div>
          <EditorSidebar
            config={config}
            updateConfig={updateConfig}
            updateConfig2={updateConfig2}
          />
        </PanelInteractContextProvider>
      </PanelRenderedConfigContextProvider>
    </ThemeProvider>
  );
};

export default PagePanel;
