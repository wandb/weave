import {produce} from 'immer';
import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react';

import {initializeEmptyConfig} from './state';
import {EvaluationExplorationConfig} from './types';

const EvaluationExplorerPageContext = createContext<{
  config: EvaluationExplorationConfig;
  editConfig: (fn: (draft: EvaluationExplorationConfig) => void) => void;
} | null>(null);

export const useEvaluationExplorerPageContext = () => {
  const res = useContext(EvaluationExplorerPageContext);
  if (res == null) {
    throw new Error('EvaluationExplorerPageContext not found');
  }
  return res;
};

const freeze = <T,>(val: T): T => {
  return produce(val, draft => {
    return;
  });
};

export const EvaluationExplorerPageProvider: React.FC<{
  children: React.ReactNode;
}> = ({children}) => {
  const frozenConfig = useMemo(() => {
    return freeze(initializeEmptyConfig());
  }, []);
  const [config, setConfig] =
    useState<EvaluationExplorationConfig>(frozenConfig);

  const editConfig = useCallback(
    (fn: (draft: EvaluationExplorationConfig) => void) => {
      setConfig(produce(config, fn));
    },
    [config]
  );

  return (
    <EvaluationExplorerPageContext.Provider value={{config, editConfig}}>
      {children}
    </EvaluationExplorerPageContext.Provider>
  );
};
