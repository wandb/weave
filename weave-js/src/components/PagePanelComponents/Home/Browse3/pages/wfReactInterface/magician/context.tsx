import React, {createContext, useContext, useMemo, useState} from 'react';

import {useGetTraceServerClientContext} from '../traceServerClientContext';
import {EntityProject, MagicContextValue} from './types';

const DEFAULT_MODEL = 'coreweave/moonshotai/Kimi-K2-Instruct';

const MagicContext = createContext<MagicContextValue | undefined>(undefined);

export const useMagicContext = () => {
  const context = useContext(MagicContext);
  if (!context) {
    throw new Error('useMagicContext must be used within MagicProvider');
  }
  return context;
};

export const MagicProvider: React.FC<{
  value: EntityProject;
  children: React.ReactNode;
}> = ({value, children}) => {
  const client = useGetTraceServerClientContext()();
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);

  if (!client) {
    throw new Error('No trace server client found');
  }

  const magicContextValue = useMemo(
    () => ({
      entity: value.entity,
      project: value.project,
      selectedModel,
      setSelectedModel,
    }),
    [value.entity, value.project, selectedModel]
  );

  return (
    <MagicContext.Provider value={magicContextValue}>
      {children}
    </MagicContext.Provider>
  );
};
