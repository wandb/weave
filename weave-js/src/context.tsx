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
  // The following flags:
  //
  // * clientEvalInUseNodeValueEnabled
  // * refinementInReactHooksDisabled
  // * sidebarConfigStylingEnabled
  // * errorBoundaryInPanelComp2Enabled
  // * redesignedPlotConfigEnabled
  //
  // are all feature flags that were previously bound to `dashUi`, but have
  // been refactored out. They are ALL instances of bad tech debt, and should
  // be removed once we're confident that the new behavior is stable. In
  // particular, we need to get rid of these to actually integrate Weave in
  // the app. We need to systematically remove all of these flags. Some of
  // them are easy to remove: for example, `redesignedPlotConfigEnabled`,
  // while others will require UI work, like `sidebarConfigStylingEnabled` -
  // this requires unifying the config bar for Weave panels in workspaces and
  // reports with that of the weave homepage. Finally, some like
  // `refinementInReactHooksDisabled` are particularly hard because the
  // condition for the flag depends on more subtle concepts like whether or
  // not a node is constructed in the react code.
  clientEvalInUseNodeValueEnabled?: boolean;
  refinementInReactHooksDisabled?: boolean;
  sidebarConfigStylingEnabled?: boolean;
  errorBoundaryInPanelComp2Enabled?: boolean;
  redesignedPlotConfigEnabled?: boolean; // we might just want to use `sidebarConfigStylingEnabled` here.
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
  // See comment on `WeaveFeatures` - we should not introduce more uses of this.
  return !!useContext(WeaveFeaturesContext).clientEvalInUseNodeValueEnabled;
};

export const useWeaveRefinementInReactHooksDisabled = () => {
  // See comment on `WeaveFeatures` - we should not introduce more uses of this.
  return !!useContext(WeaveFeaturesContext).refinementInReactHooksDisabled;
};

export const useWeaveSidebarConfigStylingEnabled = () => {
  // See comment on `WeaveFeatures` - we should not introduce more uses of this.
  return !!useContext(WeaveFeaturesContext).sidebarConfigStylingEnabled;
};

export const useWeaveErrorBoundaryInPanelComp2Enabled = () => {
  // See comment on `WeaveFeatures` - we should not introduce more uses of this.
  return !!useContext(WeaveFeaturesContext).errorBoundaryInPanelComp2Enabled;
};

export const useWeaveRedesignedPlotConfigEnabled = () => {
  // See comment on `WeaveFeatures` - we should not introduce more uses of this.
  return !!useContext(WeaveFeaturesContext).redesignedPlotConfigEnabled;
};
