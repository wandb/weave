/* Panels produce default configs in non-standard and async ways. This let's us capture them.
   However, it'd be better to standardize on async panel initializers that we can just call,
   instead of needing to log additional state into this context.
   TODO: fix.
*/

import React, {useCallback, useContext, useEffect, useState} from 'react';

import {consoleLog} from '../../util';
import {usePanelContext} from './PanelContext';

export interface PanelRenderedConfigContextState {
  // State is stored by panel path. panel path is managed by PanelContext.
  panelConfig: {[pathString: string]: any};
}

export interface PanelRenderedConfigContextValue {
  state: PanelRenderedConfigContextState;
  setState: (
    newState: (
      prevState: PanelRenderedConfigContextState
    ) => PanelRenderedConfigContextState
  ) => void;
}

export const PanelRenderedConfigContext =
  React.createContext<PanelRenderedConfigContextValue | null>(null);
PanelRenderedConfigContext.displayName = 'PanelRenderedConfigContext';

export const PanelRenderedConfigContextProvider: React.FC = React.memo(
  ({children}) => {
    const [state, setState] = useState<PanelRenderedConfigContextState>({
      panelConfig: {},
    });
    consoleLog('RENDERED CONFIG CONTEXT', state);

    return (
      <PanelRenderedConfigContext.Provider value={{state, setState}}>
        {children}
      </PanelRenderedConfigContext.Provider>
    );
  }
);
PanelRenderedConfigContextProvider.displayName =
  'PanelRenderedConfigContextProvider';

const usePanelRenderedConfigContext = () => {
  const context = useContext(PanelRenderedConfigContext);
  if (context == null) {
    throw new Error(
      'usePanelRenderedConfigContext must be used within a PanelInteractContextProvider'
    );
  }
  return context;
};

export const usePanelRenderedConfigByPath = (path: string[]) => {
  const {state} = usePanelRenderedConfigContext();
  const pathString = path.join('.');
  return state.panelConfig[pathString];
};

export const usePanelRenderedConfig = () => {
  const {path} = usePanelContext();
  return usePanelRenderedConfigByPath(path);
};

const useSetPanelRenderedConfigByPath = () => {
  const {setState} = usePanelRenderedConfigContext();

  return useCallback(
    (path: string[], config: any) => {
      const pathString = path.join('.');
      setState(prevState => {
        consoleLog('SETTING');
        return {
          ...prevState,
          panelConfig: {
            ...prevState.panelConfig,
            [pathString]: config,
          },
        };
      });
    },
    [setState]
  );
};

export const useSetPanelRenderedConfig = (config: any) => {
  const setPanelRenderedConfig = useSetPanelRenderedConfigByPath();
  const {path} = usePanelContext();

  useEffect(() => {
    consoleLog('SET PANEL RENDERED CONFIG', config);
    setPanelRenderedConfig(path, config);
  }, [config, path, setPanelRenderedConfig]);
};
