import {Client} from '@wandb/weave/core';
import React, {FC, createContext, useContext, useMemo} from 'react';
import _ from 'lodash';

import {WeaveApp} from './weave';

export interface ClientState {
  client?: Client;
}

// minimal allow-list of feature flags mapping to beta feature flags.
export type WeaveWBBetaFeatures = {
  'weave-python-ecosystem'?: boolean;
  'weave-devpopup'?: boolean;
};

export type PanelSettingPanel = 'JupyterViewer';

export interface WeaveFeatures {
  actions?: boolean;
  fullscreenMode?: boolean;
  betaFeatures: WeaveWBBetaFeatures;
  panelSettings?: Record<PanelSettingPanel, unknown>;
  dashUi?: boolean;
  // `clientEvalInUseNodeValueEnabled` was previously bound to `dashUi`, but has been refactored out.
  // We should remove this flag once we're confident that the new behavior is stable.
  clientEvalInUseNodeValueEnabled?: boolean;
  // `refinementInReactHooksDisabled` was previously bound to `dashUi`, but has been refactored out.
  // We should remove this flag once we're confident that the new behavior is stable.
  refinementInReactHooksDisabled?: boolean;
  // `sidebarConfigStylingEnabled` was previously bound to `dashUi`, but has been refactored out.
  // We should remove this flag once we're confident that the new behavior is stable.
  sidebarConfigStylingEnabled?: boolean;
  // `errorBoundaryInPanelComp2Enabled` was previously bound to `dashUi`, but has been refactored out.
  // We should remove this flag once we're confident that the new behavior is stable.
  errorBoundaryInPanelComp2Enabled?: boolean;
  // `enableRedesignedPlotConfigEnabled` was previously bound to `dashUi`, but has been refactored out.
  // We should remove this flag once we're confident that the new behavior is stable.
  enableRedesignedPlotConfigEnabled?: boolean;
}

export const ClientContext = React.createContext<ClientState>({
  client: undefined,
});
ClientContext.displayName = 'ClientContext';

export const WeaveContext = createContext<WeaveApp | null>(null);
WeaveContext.displayName = 'WeaveContext';

export const useWeaveContext = () => {
  const clientContext = useContext(ClientContext);
  const {client} = clientContext;
  if (client == null) {
    throw new Error(
      'Component calling useWeaveContext must have cgreact.ClientContext ancestor'
    );
  }
  return useMemo(() => new WeaveApp(client), [client]);
};

export const WeaveFeaturesContext = createContext<WeaveFeatures>({
  betaFeatures: {},
});
WeaveFeaturesContext.displayName = 'WeaveFeaturesContext';

export const WeaveFeaturesContextProvider: FC<{features: WeaveFeatures}> =
  React.memo(props => {
    const prevFeatures = {...useWeaveFeaturesContext()};

    // for panelSettings, we can't do a simple spread operator combine, since we
    // need to retain values from both panelSettings if they exist. Spread operator
    // will only retain the props.features copy of panelSettings, ignoring any panelSettings
    // in prevFeatures.
    const newFeatures = _.merge(prevFeatures, props.features);

    return (
      <WeaveFeaturesContext.Provider value={newFeatures}>
        {props.children}
      </WeaveFeaturesContext.Provider>
    );
  });

export const useWeaveFeaturesContext = () => {
  return useContext(WeaveFeaturesContext);
};

export const usePanelSettings = (type: PanelSettingPanel) => {
  return useWeaveFeaturesContext().panelSettings?.[type] ?? {};
};

export const useWeaveClientEvalInUseNodeValueEnabled = () => {
  return !!useContext(WeaveFeaturesContext).clientEvalInUseNodeValueEnabled;
};

export const useWeaveRefinementInReactHooksDisabled = () => {
  return !!useContext(WeaveFeaturesContext).refinementInReactHooksDisabled;
};

export const useWeaveSidebarConfigStylingEnabled = () => {
  return !!useContext(WeaveFeaturesContext).sidebarConfigStylingEnabled;
};

export const useWeaveErrorBoundaryInPanelComp2Enabled = () => {
  return !!useContext(WeaveFeaturesContext).errorBoundaryInPanelComp2Enabled;
};

export const useWeaveRedesignedPlotConfigEnabled = () => {
  return !!useContext(WeaveFeaturesContext).enableRedesignedPlotConfigEnabled;
};
