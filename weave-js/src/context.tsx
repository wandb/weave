import {Client} from '@wandb/weave/core';
import _ from 'lodash';
import React, {createContext, FC, useContext, useMemo} from 'react';

import {PanelInteractContextProvider} from './components/Panel2/PanelInteractContext';
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
  // Deprecated. Do not introduce new uses of this flag.
  dashUi?: boolean;
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
  // reports with that of the weave homepage (or at least setting the context
  // var based on the sidebar styling itself, not `isDash`). Finally, some like
  // `refinementInReactHooksDisabled` are particularly hard because the
  // condition for the flag depends on more subtle concepts like whether or not
  // a node is constructed in the react code.
  //
  // `clientEvalInUseNodeValueEnabled` refactor suggestion: determine why this
  // is presumably only usable in the weave app and not in main app. My hunch is
  // that this is OK to have ON in the main app, but we need to verify. If so,
  // just enable everywhere and remove the conditions. It might be only ok under
  // the condition that we are using weave1 backend. If so, then we should
  // change the caller's condition to be based on the weave1 backend.
  clientEvalInUseNodeValueEnabled?: boolean;
  //
  // `refinementInReactHooksDisabled` refactor suggestion: this one is hard. My
  // belief is that we can safely disable refinement almost always (since
  // ChildPanel and ExpressionEditor both refine their expressions before
  // passing them on to child components). However, in the case that we
  // construct the graph in react code itself (manually calling ops), then we
  // actually need to refine. The problem is determining if a graph has an
  // ancestor node that is manually constructed, or if it is constructed as part
  // of the expression editor, and refined. In fact, i think this is currently
  // buggy, but we don't show any panels in the weave app that have in-component
  // graph construction so we get lucky. We should fix this, and then remove
  // this flag.
  refinementInReactHooksDisabled?: boolean;
  //
  // `sidebarConfigStylingEnabled` refactor suggestion: This is easier.
  // Essentially a number of config components are styled differently based on
  // this flag. The weave app config bar is a sticky, full-height bar that has
  // fixed width and scrolls internally. In contrast, the main app uses a
  // floating modal that is unbounded in height. This difference creates
  // inconsistencies in the styling of the config components. We should probably
  // fix the modal config to have the same fixed width and scrolling behavior as
  // the weave app, and then remove this flag.
  sidebarConfigStylingEnabled?: boolean;
  //
  // `errorBoundaryInPanelComp2Enabled` refactor suggestion: This one is
  // interesting. In the main app, we have error boundaries at the boundary
  // between the app and weave panels (ex. RootQueryPanel or ArtifactHomepage).
  // In contrast, the Weave app puts error boundaries at each `PanelComp2`
  // layer. The benefit of the app experience is that we more intelligently
  // handle "undos" when an error occurs. This should not be hard to resolve,
  // just need to take the time to do it.
  errorBoundaryInPanelComp2Enabled?: boolean;
  //
  // `redesignedPlotConfigEnabled` refactor suggestion: This one is easy. When
  // refactoring panel plot, we were conservative and did not want to change the
  // behavior of the main app. My reading though is that all the changes are
  // valid and good. We should audit the callsites and make 1 of two changes for
  // each one: 1) if the callsite effects the config, change it to
  // `sidebarConfigStylingEnabled`; 2) if the callsite is something else, just
  // remove it.
  redesignedPlotConfigEnabled?: boolean;
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

    // PanelInteractContext is placed here since it belongs at the root level
    // of any component tree that renders Weave Panels. It is used most often
    // by ChildPanel.

    return (
      <WeaveFeaturesContext.Provider value={newFeatures}>
        <PanelInteractContextProvider>
          {props.children}
        </PanelInteractContextProvider>
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
