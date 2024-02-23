import React, {createContext, FC, useContext, useMemo} from 'react';

import {cgDataModelInterface} from './compute_graph_interface';
import {WFDataModelHooks} from './interface';
import {tsDataModelInterface} from './trace_server_interface';

const TRACE_SERVER_SUPPORTS_OBJECTS = false;

const WFDataModelHooksContext = createContext<WFDataModelHooks | null>(null);

export const useWFHooks = () => {
  const ctx = useContext(WFDataModelHooksContext);
  if (ctx === null) {
    throw new Error('No WFDataModelHooksContext');
  }
  return ctx;
};

const WFDataModelFromComputeGraphProvider: FC = ({children}) => {
  return (
    <WFDataModelHooksContext.Provider value={cgDataModelInterface}>
      {children}
    </WFDataModelHooksContext.Provider>
  );
};

const WFDataModelFromTraceServerProvider: FC = ({children}) => {
  return (
    <WFDataModelHooksContext.Provider value={tsDataModelInterface}>
      {children}
    </WFDataModelHooksContext.Provider>
  );
};

const WFDataModelFromTraceServerCallsOnlyProvider: FC = ({children}) => {
  const mixedContext: WFDataModelHooks = useMemo(() => {
    return {
      useCall: tsDataModelInterface.useCall,
      useCalls: tsDataModelInterface.useCalls,
      useOpVersion: cgDataModelInterface.useOpVersion,
      useOpVersions: cgDataModelInterface.useOpVersions,
      useObjectVersion: cgDataModelInterface.useObjectVersion,
      useRootObjectVersions: cgDataModelInterface.useRootObjectVersions,
      derived: {
        useChildCallsForCompare:
          tsDataModelInterface.derived.useChildCallsForCompare,
      },
    };
  }, []);
  return (
    <WFDataModelHooksContext.Provider value={mixedContext}>
      {children}
    </WFDataModelHooksContext.Provider>
  );
};

export const WFDataModelAutoProvider: FC<{
  entityName: string;
  projectName: string;
}> = ({entityName, projectName, children}) => {
  const hasCGData = useProjectHasCGData(entityName, projectName);
  const hasTSData = useProjectHasTSData(entityName, projectName);

  if (hasCGData) {
    return (
      <WFDataModelFromComputeGraphProvider>
        {children}
      </WFDataModelFromComputeGraphProvider>
    );
  } else if (hasTSData) {
    if (TRACE_SERVER_SUPPORTS_OBJECTS) {
      return (
        <WFDataModelFromTraceServerProvider>
          {children}
        </WFDataModelFromTraceServerProvider>
      );
    }
    return (
      <WFDataModelFromTraceServerCallsOnlyProvider>
        {children}
      </WFDataModelFromTraceServerCallsOnlyProvider>
    );
  }

  // Default to CG
  return (
    <WFDataModelFromComputeGraphProvider>
      {children}
    </WFDataModelFromComputeGraphProvider>
  );
};

const useProjectHasCGData = (entity: string, project: string) => {
  const calls = cgDataModelInterface.useCalls(entity, project, {}, 1);
  return (calls.result ?? []).length > 0;
};

const useProjectHasTSData = (entity: string, project: string) => {
  const calls = tsDataModelInterface.useCalls(entity, project, {}, 1);
  return (calls.result ?? []).length > 0;
};

export const useIsWeaveflowEnabled = (
  entityName: string,
  projectName: string
) => {
  const hasCGData = useProjectHasCGData(entityName, projectName);
  const hasTSData = useProjectHasTSData(entityName, projectName);
  return hasCGData || hasTSData;
};
