import Loader from '@wandb/weave/common/components/WandbLoader';
import * as globals from '@wandb/weave/common/css/globals.styles';
import {NodeOrVoidNode, voidNode} from '@wandb/weave/core';
import {produce} from 'immer';
import React, {FC, useCallback, useEffect, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {Icon} from 'semantic-ui-react';
import styled, {ThemeProvider} from 'styled-components';

import {getCookie} from '../common/util/cookie';
import getConfig from '../config';
import {useWeaveContext} from '../context';
import {
  useIsAuthenticated,
  useIsSignupRequired,
  useWeaveViewer,
} from '../context/WeaveViewerContext';
import {
  datadogSetUserInfo,
  DDUserInfoType,
} from '../integrations/analytics/datadog';
import {useNodeWithServerType} from '../react';
import {consoleLog} from '../util';
import {trackPage} from '../util/events';
import {urlWandbFrontend} from '../util/urls';
import {useWeaveAutomation} from './automation';
import {BetaIndicator} from './PagePanelComponents/BetaIndicator';
import {HelpCTA} from './PagePanelComponents/HelpCTA';
import {Home} from './PagePanelComponents/Home/Home';
import {useCopyCodeFromURI} from './PagePanelComponents/hooks';
import {PersistenceManager} from './PagePanelComponents/PersistenceManager';
import {
  inJupyterCell,
  isServedLocally,
  uriFromNode,
  weaveTypeIsPanel,
  weaveTypeIsPanelGroup,
} from './PagePanelComponents/util';
import {
  PagePanelControlContextProvider,
  usePagePanelControlRequestedActions,
} from './PagePanelContext';
import {
  CHILD_PANEL_DEFAULT_CONFIG,
  ChildPanel,
  ChildPanelConfigComp,
  ChildPanelFullConfig,
} from './Panel2/ChildPanel';
import {ChildPanelExportReport} from './Panel2/ChildPanelExportReport/ChildPanelExportReport';
import {themes} from './Panel2/Editor.styles';
import {
  IconClose,
  IconHome,
  IconOpenNewTab,
  IconPencilEdit,
} from './Panel2/Icons';
import * as Styles from './Panel2/PanelExpression/styles';
import {
  PanelInteractContextProvider,
  useCloseDrawer,
  usePanelInteractMode,
  useSetInteractingPanel,
} from './Panel2/PanelInteractContext';
import {PanelRenderedConfigContextProvider} from './Panel2/PanelRenderedConfigContext';
import PanelInteractDrawer from './Sidebar/PanelInteractDrawer';

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
JupyterControlsHelpText.displayName = 'S.JupyterControlsHelpText';

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
JupyterControlsMain.displayName = 'S.JupyterControlsMain';

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
JupyterControlsIcon.displayName = 'S.JupyterControlsIcon';

const HOST_SESSION_ID_COOKIE = `host_session_id`;

function useEnablePageAnalytics() {
  const history = useHistory();
  const pathRef = useRef('');
  const {urlPrefixed, backendWeaveViewerUrl} = getConfig();
  const weaveViewer = useWeaveViewer();

  const trackOnPathDiff = useCallback(
    (location: any, options: any) => {
      const currentPath = `${location.pathname}${location.search}`;
      const fullURL = `${window.location.protocol}//${window.location.host}${location.pathname}${location.search}${location.hash}`;
      if (pathRef.current !== currentPath) {
        let pageCategory = '';
        if (location.search.includes('exp=get')) {
          pageCategory = 'WeaveGetExpression';
        } else if (location.pathname.includes('/browse')) {
          pageCategory = 'WeaveBrowser';
        }
        trackPage({url: fullURL, pageCategory}, options);
        pathRef.current = currentPath;
      }
    },
    [pathRef]
  );

  // fetch user
  useEffect(() => {
    if (!weaveViewer.loading) {
      const injector = (window as any).WBAnalyticsInjector;
      if (injector) {
        const authenticated = !!weaveViewer.data.authenticated;
        // In Weave, we only want to inject analytics if the user is authenticated.
        // This means we don't have to muck with the consent banner.
        if (authenticated) {
          try {
            injector.initializeTrackingScripts(authenticated).finally(() => {
              (window.analytics as any)?.identify(
                weaveViewer.data.user_id ?? ''
              );
            });
          } catch (e) {
            // console.error('Failed to inject analytics', e);
          }
        }
      }
    }
  }, [urlPrefixed, backendWeaveViewerUrl, weaveViewer]);

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

const useInitializeDataDog = () => {
  const weaveViewer = useWeaveViewer();

  useEffect(() => {
    if (weaveViewer.loading) {
      return;
    }
    const userInfo: DDUserInfoType = {};
    if (weaveViewer.data.authenticated && weaveViewer.data.user_id) {
      userInfo.username = weaveViewer.data.user_id;
    }
    datadogSetUserInfo(userInfo);
  }, [weaveViewer]);
};

type PagePanelProps = {
  browserType: string | undefined;
};

const PagePanel = ({browserType}: PagePanelProps) => {
  useEnablePageAnalytics();
  useInitializeDataDog();
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
  const signupRequired = useIsSignupRequired();
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
    if (signupRequired) {
      const newOrigin = urlWandbFrontend();
      const newUrl = `${newOrigin}/signup`;
      // eslint-disable-next-line wandb/no-unprefixed-urls
      window.location.replace(newUrl);
      return;
    }
    if (needsLogin) {
      const newOrigin = window.WEAVE_CONFIG.WANDB_BASE_URL;
      const newUrl = `${newOrigin}/oidc/login?${new URLSearchParams({
        redirect_to: window.location.href,
      }).toString()}`;
      // eslint-disable-next-line wandb/no-unprefixed-urls
      window.location.replace(newUrl);
    }
  }, [authed, isLocal, needsLogin, signupRequired]);

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
            {!inJupyter && <HelpCTA />}
            {!inJupyter && <BetaIndicator />}
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
  const panelInteractMode = usePanelInteractMode();
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
    <PagePanelControlContextProvider>
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
        <PanelInteractDrawer active={panelInteractMode !== null}>
          {panelInteractMode === 'config' && (
            <ChildPanelConfigComp
              config={config}
              updateConfig={updateConfig}
              updateConfig2={updateConfig2}
            />
          )}
          {panelInteractMode === 'export-report' && (
            <ChildPanelExportReport rootConfig={config} />
          )}
        </PanelInteractDrawer>
        {inJupyter && (
          <JupyterPageControls
            {...props}
            reveal={showJupyterControls && panelInteractMode === null}
            goHome={goHome}
            openNewTab={openNewTab}
            maybeUri={maybeUri}
            isGroup={isGroup}
            isPanel={isPanel}
            updateConfig2={updateConfig2}
          />
        )}
      </PageContentContainer>
    </PagePanelControlContextProvider>
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
  const setInteractingPanel = useSetInteractingPanel();
  const closeDrawer = useCloseDrawer();
  const panelInteractMode = usePanelInteractMode();
  const requestedActions = usePagePanelControlRequestedActions();

  return (
    <JupyterControlsMain
      reveal={props.reveal}
      onMouseLeave={e => {
        setHoverText('');
      }}>
      <JupyterControlsHelpText active={hoverText !== ''}>
        {hoverText}
      </JupyterControlsHelpText>

      {Object.entries(requestedActions).map(([key, val]) => {
        return (
          <JupyterControlsIcon
            key={key}
            onClick={val.onClick}
            onMouseEnter={e => {
              setHoverText(val.label);
            }}
            onMouseLeave={e => {
              setHoverText('');
            }}>
            {val.Icon}
          </JupyterControlsIcon>
        );
      })}

      {panelInteractMode !== null ? (
        <JupyterControlsIcon
          onClick={() => {
            closeDrawer();
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
            setInteractingPanel('config', ['']);
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
WeaveRoot.displayName = 'S.WeaveRoot';

const PageContentContainer = styled.div`
  flex: 1 1 300px;
  overflow: hidden;
  display: flex;
`;
PageContentContainer.displayName = 'S.PageContentContainer';
