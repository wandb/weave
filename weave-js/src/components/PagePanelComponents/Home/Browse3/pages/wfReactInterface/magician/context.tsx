import React, {createContext, useContext, useMemo, useState} from 'react';

import {useGetTraceServerClientContext} from '../traceServerClientContext';
import {EntityProject, MagicContextValue} from './types';

/** Default model to use when no model is selected */
const DEFAULT_MODEL = 'coreweave/moonshotai/Kimi-K2-Instruct';

/** React context for magic-related state (entity, project, selected model) */
const MagicContext = createContext<MagicContextValue | undefined>(undefined);

/**
 * Hook to access the magic context.
 * 
 * Provides access to entity, project, selected model, and model setter.
 * Must be used within a MagicProvider.
 * 
 * @returns The magic context value
 * @throws Error if used outside of MagicProvider
 * 
 * @example
 * ```tsx
 * const { entity, project, selectedModel, setSelectedModel } = useMagicContext();
 * ```
 */
export const useMagicContext = () => {
  const context = useContext(MagicContext);
  if (!context) {
    throw new Error('useMagicContext must be used within MagicProvider');
  }
  return context;
};

/**
 * Provider component that supplies magic context to its children.
 * 
 * Manages global state for entity/project and model selection.
 * Must be used at the top level of your magic-enabled components.
 * 
 * @param value Entity and project configuration
 * @param children React components that will have access to magic context
 * 
 * @example
 * ```tsx
 * <MagicProvider value={{ entity: 'my-org', project: 'my-project' }}>
 *   <MyMagicComponent />
 * </MagicProvider>
 * ```
 */
export const MagicProvider: React.FC<{
  /** Entity and project configuration */
  value: EntityProject;
  /** React components that will have access to magic context */
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
