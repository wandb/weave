import {Client} from '@wandb/weave/core';
import React, {createContext, useContext, useMemo} from 'react';

import {WeaveApp} from './weave';

export interface ClientState {
  client?: Client;
}

// minimal allow-list of feature flags mapping to beta feature flags.
export type WeaveWBBetaFeatures = {
  'weave-python-ecosystem'?: boolean;
  'weave-devpopup'?: boolean;
};

export interface WeaveFeatures {
  actions?: boolean;
  fullscreenMode?: boolean;
  dashUi?: boolean;
  betaFeatures: WeaveWBBetaFeatures;
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

export const useWeaveFeaturesContext = () => {
  return useContext(WeaveFeaturesContext);
};

export const useWeaveDashUiEnable = () => {
  return useContext(WeaveFeaturesContext).dashUi;
};
