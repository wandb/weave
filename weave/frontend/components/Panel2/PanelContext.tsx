/* This is nestable context available to Panel2 panels */

import React, {useContext, useMemo} from 'react';
import makeComp from '@wandb/common/util/profiler';
import * as Code from '@wandb/cg/browser/code';

export interface PanelContextState {
  frame: Code.Frame;
}

export const PanelContext = React.createContext<PanelContextState>({
  frame: {},
});

export const PanelContextProvider: React.FC<{
  newVars: Code.Frame;
}> = makeComp(
  ({newVars, children}) => {
    const {frame} = useContext(PanelContext);
    const frameValue = useMemo(() => {
      return {frame: {...frame, ...newVars}};
    }, [frame, newVars]);

    return (
      <PanelContext.Provider value={frameValue}>
        {children}
      </PanelContext.Provider>
    );
  },
  {id: 'PanelContextProvider', memo: true}
);

export function usePanelContext() {
  return useContext(PanelContext);
}
