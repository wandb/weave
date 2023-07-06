import React, {useContext} from 'react';
import {ChildPanelConfig, ChildPanelFullConfig} from './ChildPanel';

export interface PanelPanelContextValue {
  config: ChildPanelFullConfig;
  updateConfig: (config: ChildPanelFullConfig) => void;
  updateConfig2: (
    change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig
  ) => void;
}
/**
 * This context is used by PanelPanel to provide all child panels with the
 * correct functions to update the config through the overflow menu(ie OutlineItemPopupMenu).
 */
export const PanelPanelContext = React.createContext<PanelPanelContextValue>({
  // this is equivalent to CHILD_PANEL_DEFAULT_CONFIG
  // cant import this as it gives the error that CHILD_PANEL_DEFAULT_CONFIG is not defined yet
  config: {
    vars: {},
    input_node: {nodeType: 'void', type: 'invalid'},
    id: '',
    config: undefined,
  },
  updateConfig: () => {},
  updateConfig2: () => {},
});

export const PanelPanelContextProvider: React.FC<{
  config: ChildPanelFullConfig;
  updateConfig: (config: ChildPanelFullConfig) => void;
  updateConfig2: (
    change: (oldConfig: ChildPanelConfig) => ChildPanelFullConfig
  ) => void;
}> = React.memo(({config, updateConfig, updateConfig2, children}) => {
  return (
    <PanelPanelContext.Provider
      value={{
        config,
        updateConfig,
        updateConfig2,
      }}>
      {children}
    </PanelPanelContext.Provider>
  );
});

export const usePanelPanelContext = () => {
  const context = useContext(PanelPanelContext);
  if (context == null) {
    throw new Error(
      'usePanelInteractContext must be used within a PanelInteractContextProvider'
    );
  }
  return context;
};
