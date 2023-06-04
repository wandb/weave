import React from 'react';

import {
  NodeAction,
  WeaveActionsContextProviderProps,
  WeaveActionsContextState,
} from './types';

class WeaveActionsContextImpl implements WeaveActionsContextState {
  constructor(readonly actions: NodeAction[] = []) {}

  withNewActions(actions: NodeAction[]) {
    return new WeaveActionsContextImpl(this.actions.concat(actions));
  }
}

const emptyActionsContext = new WeaveActionsContextImpl();

const WeaveActionsContext = React.createContext(emptyActionsContext);
WeaveActionsContext.displayName = 'WeaveActionsContext';

// Exported mostly for debug purposes.  In general, you should use
// WeaveActionContextProvider to build on the existing actions context.
export const useWeaveActionContext = () =>
  React.useContext(WeaveActionsContext);

export const WeaveActionContextProvider: React.FC<
  WeaveActionsContextProviderProps
> = ({newActions, children}: WeaveActionsContextProviderProps) => {
  const prevContext = React.useContext(WeaveActionsContext);
  const newContext = prevContext.withNewActions(newActions);

  return (
    <WeaveActionsContext.Provider value={newContext}>
      {children}
    </WeaveActionsContext.Provider>
  );
};
