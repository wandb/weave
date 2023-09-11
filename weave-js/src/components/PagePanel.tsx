import Loader from '@wandb/weave/common/components/WandbLoader';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {NodeOrVoidNode, voidNode} from '@wandb/weave/core';
import {produce} from 'immer';
import React, {FC, useCallback, useEffect, useRef, useState} from 'react';
import {Icon} from 'semantic-ui-react';
import styled, {ThemeProvider} from 'styled-components';
import getConfig from '../config';

import {useWeaveContext} from '../context';
import {useNodeWithServerType} from '../react';
import {Home} from './PagePanelComponents/Home/Home';
import {PersistenceManager} from './PagePanelComponents/PersistenceManager';
import {useCopyCodeFromURI} from './PagePanelComponents/hooks';
import {
  inJupyterCell,
  isServedLocally,
  uriFromNode,
  useIsAuthenticated,
  weaveTypeIsPanel,
  weaveTypeIsPanelGroup,
} from './PagePanelComponents/util';
import {
  CHILD_PANEL_DEFAULT_CONFIG,
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
} from './Panel2/ChildPanel';
import {themes} from './Panel2/Editor.styles';
import {
  IconAddNew,
  IconClose,
  IconHome,
  IconOpenNewTab,
  IconPencilEdit,
} from './Panel2/Icons';
import * as Styles from './Panel2/PanelExpression/styles';
import {
  PANEL_GROUP_DEFAULT_CONFIG,
  addPanelToGroupConfig,
} from './Panel2/PanelGroup';
import {
  PanelInteractContextProvider,
  useCloseEditor,
  useEditorIsOpen,
  useSetInspectingPanel,
} from './Panel2/PanelInteractContext';
import {useUpdateServerPanel} from './Panel2/PanelPanel';
import {PanelRenderedConfigContextProvider} from './Panel2/PanelRenderedConfigContext';
import Inspector from './Sidebar/Inspector';
import {useWeaveAutomation} from './automation';
import {consoleLog} from '../util';
import {trackPage} from '../util/events';
import {getCookie} from '../common/util/cookie';
import {useHistory} from 'react-router-dom';

const JupyterControlsHelpText = styled.div<{active: boolean}>`
  width: max-content;
  position: absolute;
  top: 50px;
  border-radius: 4px;
  right: 48px;
  // transform: translate(-50%, 0);
  text-align: center;
  color: #fff;
  background-color: #1d1f24;
  padding: 10px 12px;
  font-size: 14px;
  opacity: 0.8;

  transition: display 0.3s ease-in-out;

  visibility: ${props => (props.active ? '' : 'hidden')};
  opacity: ${props => (props.active ? 0.8 : 0)};
  transition: visibility 0s, opacity 0.3s ease-in-out;
`;

const JupyterControlsMain = styled.div<{reveal?: boolean}>`
  position: absolute;
  top: 50%;
  right: ${props => (props.reveal ? '-0px' : '-60px')};
  transition: right 0.3s ease-in-out;
  box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
  transform: translate(0, -50%);
  width: 40px;
  background-color: white;
  border: 1px solid #ddd;
  border-right: none;
  border-radius: 8px 0px 0px 8px;
  display: flex;
  flex-direction: column;
  justify-content: space-evenly;
  align-items: center;
  gap: 8px;
  padding: 8px 0px;
  z-index: 100;
`;

const JupyterControlsIcon = styled.div`
  width: 25px;
  height: 25px;
  padding: 4px;
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  transition: background-color 0.1s ease-in-out;
  border-radius: 4px;
  &:hover {
    background: #0096ad1a;
    color: #0096ad;
  }
`;

const HOST_SESSION_ID_COOKIE = `host_session_id`;

// TODO: This should be merged with useIsAuthenticated and refactored to useWBViewer()
function useEnablePageAnalytics() {
  const history = useHistory();
  const pathRef = useRef('');
  const {urlPrefixed, backendWeaveViewerUrl} = getConfig();

  const trackOnPathDiff = useCallback(
    (location: any, options: any) => {
      const currentPath = `${location.pathname}${location.search}`;
      const fullURL = `${window.location.protocol}//${window.location.host}${location.pathname}${location.search}${location.hash}`;
      if (pathRef.current !== currentPath) {
        let pageName = '';
        if (location.search.includes('exp=get')) {
          pageName = 'WeaveBoardOrTable';
        } else if (location.pathname.includes('/browse')) {
          pageName = 'WeaveBrowser';
        }
        trackPage({url: fullURL, pageName}, options);
        pathRef.current = currentPath;
      }
    },
    [pathRef]
  );

  // fetch user
  useEffect(() => {
    const anonApiKey = getCookie('anon_api_key');
    const additionalHeaders: Record<string, string> = {};
    if (anonApiKey != null && anonApiKey !== '') {
      additionalHeaders['x-wandb-anonymous-auth-id'] = btoa(anonApiKey);
    }
    fetch(urlPrefixed(backendWeaveViewerUrl()), {
      credentials: 'include',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...additionalHeaders,
      },
    })
      .then(res => {
        if (res.status === 200) {
          return res.json();
        }
        return;
      })
      .then(json => {
        const serverUserId = json?.user_id ?? '';
        if (serverUserId !== '') {
          (window.analytics as any)?.identify(serverUserId);
        }
      })
      .catch(err => {
        console.error(err);
      });
  }, [urlPrefixed, backendWeaveViewerUrl]);

  useEffect(() => {
    const options = {
      context: {
        hostSessionID: getCookie(HOST_SESSION_ID_COOKIE),
      },
    };

    const unlisten = history.listen(location => {
      trackOnPathDiff(location, options);
    });

    // Track initial page view
    trackOnPathDiff(history.location, options);

    return () => {
      unlisten();
    };
  }, [history, trackOnPathDiff]);
}

// Simple function that forces rerender when URL changes.
const usePoorMansLocation = () => {
  const [location, setLocation] = useState(window.location.toString());

  useEffect(() => {
    const interval = setInterval(() => {
      if (window.location.toString() !== location) {
        setLocation(window.location.toString());
      }
    }, 250);
    return () => {
      clearInterval(interval);
    };
  }, [location]);

  return window.location;
};

type PagePanelProps = {
  browserType: string | undefined;
};

const PagePanel = ({browserType}: PagePanelProps) => {
  useEnablePageAnalytics();
  const weave = useWeaveContext();
  const location = usePoorMansLocation();
  const history = useHistory();
  const urlParams = new URLSearchParams(location.search);
  const fullScreen = urlParams.get('fullScreen') != null;
  const moarfullScreen = urlParams.get('moarFullScreen') != null;
  const previewMode = urlParams.get('previewMode') != null;
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
  const authed = useIsAuthenticated();
  const isLocal = isServedLocally();
  const transparentlyMountExpString = useRef('');

  const setUrlExp = useCallback(
    (exp: NodeOrVoidNode) => {
      const newExpStr = weave.expToString(exp);
      if (newExpStr === expString) {
        return;
      }

      const searchParams = new URLSearchParams(window.location.search);
      searchParams.set('exp', newExpStr);
      const pathname = inJupyterCell() ? window.location.pathname : '/';

      if (
        newExpStr.startsWith('get') &&
        expString?.startsWith('get') &&
        newExpStr.includes('local-artifact') &&
        expString.includes('wandb-artifact')
      ) {
        transparentlyMountExpString.current = newExpStr;
      }
      history.push(`${pathname}?${searchParams}`);
    },
    [expString, history, weave]
  );

  const [config, setConfig] = useState<ChildPanelFullConfig>(
    CHILD_PANEL_DEFAULT_CONFIG
  );

  // If the exp string has gone away, perhaps by back button navigation,
  // reset the config.
  useEffect(() => {
    if (!expString) {
      setConfig(CHILD_PANEL_DEFAULT_CONFIG);
    }
  }, [expString]);

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
    consoleLog('PAGE PANEL MOUNT', window.location.href);
    const doTransparently =
      expString != null && transparentlyMountExpString.current === expString;
    setLoading(!doTransparently);
    if (expString != null) {
      weave.expression(expString, []).then(res => {
        if (doTransparently) {
          updateConfig({
            input_node: res.expr as any,
          });
        } else {
          updateConfig({
            input_node: res.expr as any,
            id: panelId,
            config: panelConfig,
          } as any);
        }
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
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expString, forceRemount]);

  // Moved here from PanelExpression, not sure if working yet.
  // TODO: play/pause
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

  const goHome = React.useCallback(() => {
    updateConfig({
      vars: {},
      input_node: voidNode(),
      id: '',
      config: undefined,
    });
  }, [updateConfig]);

  const needsLogin = authed === false && isLocal === false;
  useEffect(() => {
    if (needsLogin) {
      const newOrigin = window.location.origin.replace('//weave.', '//api.');
      const newUrl = `${newOrigin}/oidc/login?${new URLSearchParams({
        redirect_to: window.location.href,
      }).toString()}`;
      // eslint-disable-next-line wandb/no-unprefixed-urls
      window.location.replace(newUrl);
    }
  }, [authed, isLocal, needsLogin]);

  if (loading || authed === undefined) {
    return <Loader name="page-panel-loader" />;
  }
  if (needsLogin) {
    // Redirect is coming, just show a loader
    return <Loader name="page-panel-loader" />;
  }

  return (
    <ThemeProvider theme={themes.light}>
      <PanelRenderedConfigContextProvider>
        <PanelInteractContextProvider>
          <WeaveRoot className="weave-root" fullScreen={fullScreen}>
            {config.input_node.nodeType === 'void' ? (
              <Home
                updateConfig={updateConfig}
                inJupyter={inJupyter}
                browserType={browserType}
              />
            ) : (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  flexDirection: 'column',
                }}>
                {(!inJupyter || moarfullScreen) && !previewMode && (
                  <PersistenceManager
                    inputNode={config.input_node}
                    inputConfig={config.config}
                    updateNode={updateInputNode}
                    goHome={goHome}
                  />
                )}
                <PageContent
                  config={config}
                  previewMode={previewMode}
                  updateConfig={updateConfig}
                  updateConfig2={updateConfig2}
                  goHome={goHome}
                />
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
          </WeaveRoot>
        </PanelInteractContextProvider>
      </PanelRenderedConfigContextProvider>
    </ThemeProvider>
  );
};

export default PagePanel;

type PageContentProps = {
  config: ChildPanelFullConfig;
  previewMode?: boolean;
  updateConfig: (newConfig: ChildPanelFullConfig) => void;
  updateConfig2: (change: (oldConfig: any) => any) => void;
  goHome: () => void;
};

export const PageContent: FC<PageContentProps> = props => {
  const {config, updateConfig, updateConfig2, goHome} = props;
  const weave = useWeaveContext();
  const editorIsOpen = useEditorIsOpen();
  const inJupyter = inJupyterCell();
  const {urlPrefixed} = getConfig();

  const typedInputNode = useNodeWithServerType(config.input_node);
  const isPanel = weaveTypeIsPanel(
    typedInputNode.result?.type || {type: 'Panel' as any}
  );
  const isGroup = weaveTypeIsPanelGroup(typedInputNode.result?.type);
  const maybeUri = uriFromNode(config.input_node);
  const {onCopy} = useCopyCodeFromURI(maybeUri);

  const [showJupyterControls, setShowJupyterControls] = useState(false);
  const jupyterControlsHoverWidth = 60;
  const pageRef = useRef<HTMLDivElement>(null);
  const onMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (inJupyter) {
        const x = e.clientX;
        const pageWidth = pageRef.current?.offsetWidth || 985;
        if (pageWidth - x < jupyterControlsHoverWidth) {
          setShowJupyterControls(true);
        } else {
          setShowJupyterControls(false);
        }
      }
    },
    [inJupyter]
  );

  const openNewTab = useCallback(() => {
    const expStr = weave
      .expToString(config.input_node)
      .replace(/\n+/g, '')
      .replace(/\s+/g, '');
    window.open(urlPrefixed(`/?exp=${encodeURIComponent(expStr)}`), '_blank');
    // window.open(
    //   urlPrefixed(
    //     `/__frontend/weave_jupyter?exp=${encodeURIComponent(
    //       expStr
    //     )}&moarFullScreen=true`
    //   ),
    //   '_blank'
    // );
  }, [config.input_node, urlPrefixed, weave]);

  return (
    <PageContentContainer
      ref={pageRef}
      onMouseLeave={e => setShowJupyterControls(false)}
      onMouseMove={onMouseMove}>
      <div
        style={{
          flex: '1 1 auto',
          overflow: 'hidden',
        }}>
        <ChildPanel
          controlBar={!isPanel && !props.previewMode ? 'editable' : 'off'}
          prefixButtons={
            <>
              {inJupyter && (
                <>
                  <Styles.BarButton onClick={openNewTab}>
                    <Icon name="external square alternate" />
                  </Styles.BarButton>
                  {maybeUri && (
                    <Styles.BarButton
                      onClick={() => {
                        onCopy();
                      }}>
                      <Icon name="copy" />
                    </Styles.BarButton>
                  )}
                </>
              )}
            </>
          }
          config={config}
          updateConfig={updateConfig}
          updateConfig2={updateConfig2}
        />
      </div>
      <Inspector active={editorIsOpen}>
        <ChildPanelConfigComp
          // pathEl={CHILD_NAME}
          config={config}
          updateConfig={updateConfig}
          updateConfig2={updateConfig2}
        />
      </Inspector>
      {inJupyter && (
        <JupyterPageControls
          {...props}
          reveal={showJupyterControls && !editorIsOpen}
          goHome={goHome}
          openNewTab={openNewTab}
          maybeUri={maybeUri}
          isGroup={isGroup}
          isPanel={isPanel}
          updateConfig2={updateConfig2}
        />
      )}
    </PageContentContainer>
  );
};

const JupyterPageControls: React.FC<
  PageContentProps & {
    reveal: boolean;
    goHome: () => void;
    openNewTab: () => void;
    maybeUri: string | null;
    isGroup: boolean;
    isPanel: boolean;
    updateConfig2: (change: (oldConfig: any) => any) => void;
  }
> = props => {
  const [hoverText, setHoverText] = useState('');
  // TODO(fix): Hiding code export temporarily as it is partially broken
  // const {copyStatus, onCopy} = useCopyCodeFromURI(props.maybeUri);
  const setInspectingPanel = useSetInspectingPanel();
  const closeEditor = useCloseEditor();
  const editorIsOpen = useEditorIsOpen();
  const updateInput = useCallback(
    (newInput: NodeOrVoidNode) => {
      props.updateConfig2(oldConfig => {
        return {
          ...oldConfig,
          input_node: newInput,
        };
      });
    },
    [props]
  );
  const updateConfigForPanelNode = useUpdateServerPanel(
    props.config.input_node,
    updateInput
  );
  const addPanelToPanel = useCallback(() => {
    if (props.isPanel) {
      props.updateConfig2(oldConfig => {
        // props.updateConfig2(oldConfig => {
        let newInnerPanelConfig: ChildPanelFullConfig;
        if (props.isGroup) {
          newInnerPanelConfig = {
            ...oldConfig.config,
            config: addPanelToGroupConfig(
              oldConfig.config.config,
              [''],
              'panel'
            ),
          };
        } else {
          newInnerPanelConfig = {
            config: addPanelToGroupConfig(
              addPanelToGroupConfig(
                PANEL_GROUP_DEFAULT_CONFIG(),
                undefined,
                'panel',
                oldConfig.config
              ),
              [''],
              'panel'
            ),
            id: 'Group',
            input_node: {
              nodeType: 'void',
              type: 'invalid',
            },
            vars: {},
          };
        }

        updateConfigForPanelNode(newInnerPanelConfig);

        return {
          ...oldConfig,
          config: newInnerPanelConfig,
        };
      });
    }
  }, [props, updateConfigForPanelNode]);

  return (
    <JupyterControlsMain
      reveal={props.reveal}
      onMouseLeave={e => {
        setHoverText('');
      }}>
      <JupyterControlsHelpText active={hoverText !== ''}>
        {hoverText}
      </JupyterControlsHelpText>

      {props.isPanel && (
        <JupyterControlsIcon
          onClick={addPanelToPanel}
          onMouseEnter={e => {
            setHoverText('Add new panel');
          }}
          onMouseLeave={e => {
            setHoverText('');
          }}>
          <IconAddNew />
        </JupyterControlsIcon>
      )}

      {editorIsOpen ? (
        <JupyterControlsIcon
          onClick={() => {
            closeEditor();
            setHoverText('Edit configuration');
          }}
          onMouseEnter={e => {
            setHoverText('Close configuration editor');
          }}
          onMouseLeave={e => {
            setHoverText('');
          }}>
          <IconClose />
        </JupyterControlsIcon>
      ) : (
        <JupyterControlsIcon
          onClick={() => {
            setInspectingPanel(['']);
            setHoverText('Close configuration editor');
          }}
          onMouseEnter={e => {
            setHoverText('Edit configuration');
          }}
          onMouseLeave={e => {
            setHoverText('');
          }}>
          <IconPencilEdit />
        </JupyterControlsIcon>
      )}
      {/* TODO: Hiding code export temporarily as it is partially broken */}
      {/* <JupyterControlsIcon
        onClick={onCopy}
        onMouseEnter={e => {
          setHoverText('Copy code');
        }}
        onMouseLeave={e => {
          setHoverText('');
        }}>
        {copyStatus === 'loading' ? (
          <IconLoading />
        ) : copyStatus === 'success' ? (
          <IconCheckmark />
        ) : (
          <IconCopy />
        )}
      </JupyterControlsIcon> */}
      <JupyterControlsIcon
        onClick={props.openNewTab}
        onMouseEnter={e => {
          setHoverText('Open in new tab');
        }}
        onMouseLeave={e => {
          setHoverText('');
        }}>
        <IconOpenNewTab />
      </JupyterControlsIcon>
      <JupyterControlsIcon
        onClick={props.goHome}
        onMouseEnter={e => {
          setHoverText('Go home');
        }}
        onMouseLeave={e => {
          setHoverText('');
        }}>
        <IconHome />
      </JupyterControlsIcon>
    </JupyterControlsMain>
  );
};

const WeaveRoot = styled.div<{fullScreen: boolean}>`
  position: ${p => (p.fullScreen ? `fixed` : `absolute`)};
  top: 0;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: ${globals.WHITE};
  color: ${globals.TEXT_PRIMARY_COLOR};
`;

const PageContentContainer = styled.div`
  flex: 1 1 300px;
  overflow: hidden;
  display: flex;
`;
