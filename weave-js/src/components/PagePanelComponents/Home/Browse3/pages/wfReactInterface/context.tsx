import React, {createContext, FC, useContext, useMemo} from 'react';

import {cgWFDataModelHooks} from './compute_graph_interface';
import {WFDataModelHooksInterface} from './interface';
import {tsWFDataModelHooks} from './trace_server_interface';

const TRACE_SERVER_SUPPORTS_OBJECTS = false;

const WFDataModelHooksContext = createContext<WFDataModelHooksInterface | null>(
  null
);

export const useWFHooks = () => {
  const ctx = useContext(WFDataModelHooksContext);
  if (ctx === null) {
    throw new Error('No WFDataModelHooksContext');
  }
  return ctx;
};

const WFDataModelFromComputeGraphProvider: FC = ({children}) => {
  return (
    <WFDataModelHooksContext.Provider value={cgWFDataModelHooks}>
      {children}
    </WFDataModelHooksContext.Provider>
  );
};

const WFDataModelFromTraceServerProvider: FC = ({children}) => {
  return (
    <WFDataModelHooksContext.Provider value={tsWFDataModelHooks}>
      {children}
    </WFDataModelHooksContext.Provider>
  );
};

const WFDataModelFromTraceServerCallsOnlyProvider: FC = ({children}) => {
  const mixedContext: WFDataModelHooksInterface = useMemo(() => {
    return {
      useCall: tsWFDataModelHooks.useCall,
      useCalls: tsWFDataModelHooks.useCalls,
      useOpVersion: cgWFDataModelHooks.useOpVersion,
      useOpVersions: cgWFDataModelHooks.useOpVersions,
      useObjectVersion: cgWFDataModelHooks.useObjectVersion,
      useRootObjectVersions: cgWFDataModelHooks.useRootObjectVersions,
      derived: {
        useChildCallsForCompare:
          tsWFDataModelHooks.derived.useChildCallsForCompare,
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
  const calls = cgWFDataModelHooks.useCalls(entity, project, {}, 1);
  return (calls.result ?? []).length > 0;
};

const useProjectHasTSData = (entity: string, project: string) => {
  const calls = tsWFDataModelHooks.useCalls(entity, project, {}, 1);
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
