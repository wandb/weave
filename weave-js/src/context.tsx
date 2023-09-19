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
  dashUi?: boolean;
  betaFeatures: WeaveWBBetaFeatures;
  panelSettings?: Record<PanelSettingPanel, unknown>;
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

// This custom provider for this context allows us to have nested instances of this
// context in a given react app. The weave team wants to allow both high level features
// that are set at a global app-wide basis, and more local features that are set in
// a specific subtree of a react app.
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

export const useWeaveDashUiEnable = () => {
  return useContext(WeaveFeaturesContext).dashUi;
};

export const usePanelSettings = (type: PanelSettingPanel) => {
  return useWeaveFeaturesContext().panelSettings?.[type] ?? {};
};
