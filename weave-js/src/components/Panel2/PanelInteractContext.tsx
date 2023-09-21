/* Non-persisted UI state. */

import React, {useCallback, useContext, useState} from 'react';

import {usePanelContext} from './PanelContext';

interface PanelInteractState {
  hovered?: boolean;
  hoveredInOutline?: boolean;
  highlightInputExpr?: boolean;
}

type PanelInteractMode = 'config' | 'export-report' | null;

export interface PanelInteractContextState {
  // State is stored by panel path. panel path is managed by PanelContext.
  panelInteractMode: PanelInteractMode;
  /**
   * Unique ID of the selected root panel. Required if
   * multiple root panels share one interact drawer.
   */
  selectedDocumentId?: string;
  selectedPath: string[];
  panelState: {[pathString: string]: PanelInteractState};
}

export interface PanelInteractContextValue {
  state: PanelInteractContextState;
  setState: (
    newState: (
      prevState: PanelInteractContextState
    ) => PanelInteractContextState
  ) => void;
}

export const PanelInteractContext =
  React.createContext<PanelInteractContextValue | null>(null);
PanelInteractContext.displayName = 'PanelInteractContext';

export const PanelInteractContextProvider: React.FC<{}> = React.memo(
  ({children}) => {
    const [state, setState] = useState<PanelInteractContextState>({
      selectedPath: [],
      panelInteractMode: null,
      panelState: {},
    });

    return (
      <PanelInteractContext.Provider value={{state, setState}}>
        {children}
      </PanelInteractContext.Provider>
    );
  }
);
PanelInteractContextProvider.displayName = 'PanelInteractContextProvider';

export const usePanelInteractContext = () => {
  const context = useContext(PanelInteractContext);
  if (context == null) {
    throw new Error(
      'usePanelInteractContext must be used within a PanelInteractContextProvider'
    );
  }
  return context;
};

const usePanelInteractStateByPath = (path: string[]) => {
  const {state} = usePanelInteractContext();
  const pathString = path.join('.');
  return state.panelState[pathString];
};

export const usePanelInputExprIsHighlightedByPath = (path: string[]) => {
  return usePanelInteractStateByPath(path)?.highlightInputExpr === true;
};

export const usePanelIsHoveredByPath = (path: string[]) => {
  return usePanelInteractStateByPath(path)?.hovered === true;
};

export const useGetPanelIsHoveredByGroupPath = (groupPath: string[]) => {
  const {state} = usePanelInteractContext();
  return (panelPath: string) => {
    const pathString = [...groupPath, panelPath].join('.');
    return state.panelState[pathString]?.hovered === true;
  };
};

export const useGetPanelIsHoveredInOutlineByGroupPath = (
  groupPath: string[]
) => {
  const {state} = usePanelInteractContext();
  return (panelPath: string) => {
    const pathString = [...groupPath, panelPath].join('.');
    return state.panelState[pathString]?.hoveredInOutline === true;
  };
};

const useSetPanelStateByPath = () => {
  const {setState} = usePanelInteractContext();

  return useCallback(
    (
      path: string[],
      changeState: (prevState: PanelInteractState) => PanelInteractState
    ) => {
      const pathString = path.join('.');
      setState(prevState => {
        return {
          ...prevState,
          panelState: {
            ...prevState.panelState,
            [pathString]: changeState(prevState.panelState[pathString]),
          },
        };
      });
    },
    [setState]
  );
};

export const useSetPanelInputExprIsHighlighted = () => {
  const setPanelState = useSetPanelStateByPath();
  return useCallback(
    (path: string[], highlight: boolean) => {
      setPanelState(path, prevState => {
        return {
          ...prevState,
          highlightInputExpr: highlight,
        };
      });
    },
    [setPanelState]
  );
};

export const useSetPanelIsHovered = () => {
  const setPanelState = useSetPanelStateByPath();
  return useCallback(
    (path: string[], hovered: boolean) => {
      setPanelState(path, prevState => {
        return {
          ...prevState,
          hovered,
        };
      });
    },
    [setPanelState]
  );
};

export const useSetPanelIsHoveredInOutline = () => {
  const setPanelState = useSetPanelStateByPath();
  return useCallback(
    (path: string[], hoveredInOutline: boolean) => {
      setPanelState(path, prevState => {
        return {
          ...prevState,
          hoveredInOutline,
        };
      });
    },
    [setPanelState]
  );
};

export const useSetInteractingPanel = () => {
  const {setState} = usePanelInteractContext();
  return useCallback(
    (mode: PanelInteractMode, path: string[], documentId?: string) => {
      setState(prevState => ({
        ...prevState,
        panelInteractMode: mode,
        selectedPath: path,
        selectedDocumentId: documentId,
      }));
    },
    [setState]
  );
};

export const useSetInteractingChildPanel = () => {
  const setInteractingPanel = useSetInteractingPanel();
  const {path} = usePanelContext();
  return useCallback(
    (mode: PanelInteractMode, childPath: string, documentId?: string) => {
      setInteractingPanel(mode, path.concat([childPath]), documentId);
    },
    [path, setInteractingPanel]
  );
};

export const useCloseDrawer = () => {
  const {setState} = usePanelInteractContext();
  return useCallback(() => {
    setState(prevState => ({
      ...prevState,
      panelInteractMode: null,
    }));
  }, [setState]);
};

export const usePanelInteractMode = () => {
  const {state} = usePanelInteractContext();
  return state.panelInteractMode;
};

export const useSelectedDocumentId = () => {
  const {state} = usePanelInteractContext();
  return state.selectedDocumentId;
};

export const useSelectedPath = () => {
  const {state} = usePanelInteractContext();
  return state.selectedPath;
};
