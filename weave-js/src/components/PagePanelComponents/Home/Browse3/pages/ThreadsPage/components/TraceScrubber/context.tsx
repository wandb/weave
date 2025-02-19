import React from 'react';

import {TraceTreeFlat} from '../../types';
import {StackContextType, StackState} from './types';

export const StackContext = React.createContext<StackContextType | null>(null);

export const useStackContext = () => {
  const context = React.useContext(StackContext);
  if (!context) {
    throw new Error(
      'useStackContext must be used within a StackContextProvider'
    );
  }
  return context;
};

export const StackContextProvider: React.FC<{
  children: React.ReactNode;
  traceTreeFlat: TraceTreeFlat;
}> = ({children, traceTreeFlat}) => {
  const [stackState, setStackState] = React.useState<StackState | null>(null);

  const buildStackForCall = React.useCallback(
    (callId: string) => {
      const stack: string[] = [];
      let currentId = callId;

      // Build stack up to root
      while (currentId) {
        stack.unshift(currentId);
        const node = traceTreeFlat[currentId];
        if (!node) {
          break;
        }
        currentId = node.parentId || '';
      }

      // Build stack down to leaves
      currentId = callId;
      while (currentId) {
        const node = traceTreeFlat[currentId];
        if (!node || node.childrenIds.length === 0) {
          break;
        }
        // Take the first child in chronological order
        const nextId = [...node.childrenIds].sort(
          (a, b) =>
            Date.parse(traceTreeFlat[a].call.started_at) -
            Date.parse(traceTreeFlat[b].call.started_at)
        )[0];
        stack.push(nextId);
        currentId = nextId;
      }

      return stack;
    },
    [traceTreeFlat]
  );

  const value = React.useMemo(
    () => ({
      stackState,
      setStackState,
      buildStackForCall,
    }),
    [stackState, buildStackForCall]
  );

  return (
    <StackContext.Provider value={value}>{children}</StackContext.Provider>
  );
};
