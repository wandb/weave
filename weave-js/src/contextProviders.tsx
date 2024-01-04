import {getCookie} from '@wandb/weave/common/util/cookie';
import {
  Client,
  createRemoteClient,
  GlobalCGEventTracker,
  makeEcosystemMixedOpStore,
  StaticOpStore,
  Weave,
} from '@wandb/weave/core';
import React, {useEffect, useMemo, useState} from 'react';

import {Spec as PanelEach} from './components/Panel2/PanelEach';
import {Spec as PanelEachColumn} from './components/Panel2/PanelEachColumn';
import {Spec as PanelExpr} from './components/Panel2/PanelExpr';
import {Spec as PanelFacet} from './components/Panel2/PanelFacet';
// import {Spec as PanelFacetTabs} from './components/Panel2/PanelFacetTabs';
import {Spec as PanelGroup} from './components/Panel2/PanelGroup';
import {Spec as PanelRootBrowser} from './components/Panel2/PanelRootBrowser/PanelRootBrowser';
import {Spec as PanelSelectEditor} from './components/Panel2/PanelSelectEditor';
// import {Spec as PanelSections} from './components/Panel2/PanelSections';
import {Spec as PanelSlider} from './components/Panel2/PanelSlider';
import {
  RowSize,
  TABLE_CONFIG_DEFAULTS,
} from './components/Panel2/PanelTable/config';
import {useLoadWeaveObjects} from './components/Panel2/weaveBackend';
import getConfig from './config';
import {ClientContext, WeaveFeatures, WeaveFeaturesContext} from './context';

let GLOBAL_CLIENT: Client | null = null;

export const getGlobalWeaveContext = () => {
  if (GLOBAL_CLIENT == null) {
    throw new Error('Global Weave Context not initialized');
  }
  return new Weave(GLOBAL_CLIENT);
};

export const ComputeGraphContextProviderFromClient: React.FC<{client: Client}> =
  React.memo(({client, children}) => {
    const context = useMemo(() => ({client}), [client]);
    GLOBAL_CLIENT = client;

    const [isLoading, setIsLoading] = useState(false);
    useEffect(() => {
      const subscription = context.client
        .loadingObservable()
        .subscribe(setIsLoading);
      return () => subscription.unsubscribe();
    }, [context]);

    return (
      <div
        data-test="compute-graph-provider"
        data-test-num-shadow-server-requests-counter={
          GlobalCGEventTracker.shadowServerRequests
        }
        className={isLoading ? 'loading cg-executing' : ''}
        style={{height: '100%'}}>
        <ClientContext.Provider value={context}>
          {children}
        </ClientContext.Provider>
      </div>
    );
  });
ComputeGraphContextProviderFromClient.displayName =
  'ComputeGraphContextProviderFromClient';

const useRemoteEcosystemClient = (
  isAdmin: boolean = false,
  tokenFunc: () => Promise<string | undefined>
) => {
  const {loading, remoteOpStore} = useLoadWeaveObjects();
  return useMemo(() => {
    if (loading || remoteOpStore == null) {
      return null;
    }
    return createRemoteClient(
      getConfig().backendWeaveExecutionUrl(),
      tokenFunc,
      isAdmin,
      makeEcosystemMixedOpStore(StaticOpStore.getInstance(), remoteOpStore),
      getCookie('anon_api_key'),
      // Always use off of window object, in case of fetch wrappers
      // Why is this as any needed all of a sudden?
      (input, init) => window.fetch(input as any, init)
    );
  }, [isAdmin, remoteOpStore, tokenFunc, loading]);
};

export const RemoteEcosystemComputeGraphContextProvider: React.FC<{
  isAdmin?: boolean;
  tokenFunc?: () => Promise<string | undefined>;
}> = React.memo(({isAdmin, tokenFunc, children}) => {
  const tf = useMemo(() => {
    const dummy = async () => undefined;
    return tokenFunc != null ? tokenFunc : dummy;
  }, [tokenFunc]);
  const client = useRemoteEcosystemClient(!!isAdmin, tf);
  if (client == null) {
    return <></>;
  }
  return (
    <ComputeGraphContextProviderFromClient
      client={client}
      children={children}
    />
  );
});
RemoteEcosystemComputeGraphContextProvider.displayName =
  'RemoteEcosystemComputeGraphContextProvider';

const UNHIDE_PANELS = [
  PanelGroup,
  PanelEachColumn,
  PanelExpr,
  PanelRootBrowser,
  PanelFacet,
  // PanelFacetTabs,
  // PanelSections,
  PanelEach,
  PanelSlider,
  PanelSelectEditor,
];

export const NotebookComputeGraphContextProvider: React.FC = React.memo(
  ({children}) => {
    // Default state when in jupyter notebook weave session
    const defaultWBFeatureState: WeaveFeatures = useMemo(
      () => ({
        actions: true,
        fullscreenMode: true,
        clientEvalInUseNodeValueEnabled: true,
        sidebarConfigStylingEnabled: true,
        errorBoundaryInPanelComp2Enabled: true,
        redesignedPlotConfigEnabled: true,
        betaFeatures: {
          'weave-python-ecosystem': true,
          'weave-devpopup': false,
        },
      }),
      []
    );

    TABLE_CONFIG_DEFAULTS.rowSize = RowSize.Small;
    for (const panel of UNHIDE_PANELS) {
      panel.hidden = false;
    }

    return (
      <WeaveFeaturesContext.Provider value={defaultWBFeatureState}>
        <RemoteEcosystemComputeGraphContextProvider>
          {children}
        </RemoteEcosystemComputeGraphContextProvider>
      </WeaveFeaturesContext.Provider>
    );
  }
);
NotebookComputeGraphContextProvider.displayName =
  'NotebookComputeGraphContextProvider';
