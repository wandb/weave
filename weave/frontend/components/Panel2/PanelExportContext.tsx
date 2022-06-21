/* This is currently only active when the weave-devpopup bio
  feature flag is enabled. You can use this context so that
  any panels inside call an addPanel method you provide. */
import React, {useMemo} from 'react';
import makeComp from '@wandb/common/util/profiler';

interface Updaters {
  addPanel(panel: any): void;
}

export const PanelExportUpdaterContext = React.createContext<Updaters>({
  addPanel: () => {},
});

export const PanelExportContextProvider: React.FC<{
  addPanel?: (panel: any) => void;
}> = makeComp(
  ({addPanel, children}) => {
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
  },
  {id: 'PanelExportContextProvider', memo: true}
);
