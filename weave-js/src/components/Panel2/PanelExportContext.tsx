/* This is currently only active when the weave-devpopup beta
  feature is enabled in settings. You can use this context so that
  any panels inside call an addPanel method you provide. */
import React, {useMemo} from 'react';

interface Updaters {
  addPanel(panel: any): void;
}

export const PanelExportUpdaterContext = React.createContext<Updaters>({
  addPanel: () => {},
});

export const PanelExportContextProvider: React.FC<{
  addPanel?: (panel: any) => void;
}> = React.memo(({addPanel, children}) => {
  const addPanelUpdater = useMemo(
    () =>
      addPanel != null
        ? addPanel
        : (panel: any) => console.log('Add panel not implemented'),

    [addPanel]
  );
  const updaters = useMemo<Updaters>(
    () => ({addPanel: addPanelUpdater}),
    [addPanelUpdater]
  );

  return (
    <PanelExportUpdaterContext.Provider value={updaters}>
      {children}
    </PanelExportUpdaterContext.Provider>
  );
});
