/**
 * This file is responsible for providing the `WFDataModelHooks` context, which
 * is the primary interface for reading data from the weaveflow data model. The
 * primary exported symbols are:
 *  - useWFHooks: used by react components to get access to the weaveflow data
 *    model.
 *  - WFDataModelAutoProvider: automatically detects the engine that backs the
 *    project and configures the context accordingly.
 */

import React, {createContext, FC, useContext, useMemo} from 'react';

import {cgWFDataModelHooks} from './cgDataModelHooks';
import {useHasTraceServerClientContext} from './traceServerClientContext';
import {tsWFDataModelHooks} from './tsDataModelHooks';
import {WFDataModelHooksInterface} from './wfDataModelHooksInterface';

//  Set this to `true` once the trace server supports objects
const TRACE_SERVER_SUPPORTS_OBJECTS = true;

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
      useCallsDeleteFunc: tsWFDataModelHooks.useCallsDeleteFunc,
      useOpVersion: cgWFDataModelHooks.useOpVersion,
      useOpVersions: cgWFDataModelHooks.useOpVersions,
      useObjectVersion: cgWFDataModelHooks.useObjectVersion,
      useRootObjectVersions: cgWFDataModelHooks.useRootObjectVersions,
      useRefsData: cgWFDataModelHooks.useRefsData,
      useApplyMutationsToRef: cgWFDataModelHooks.useApplyMutationsToRef,
      useFileContent: cgWFDataModelHooks.useFileContent,
      derived: {
        useChildCallsForCompare:
          tsWFDataModelHooks.derived.useChildCallsForCompare,
        useGetRefsType: cgWFDataModelHooks.derived.useGetRefsType,
        useRefsType: cgWFDataModelHooks.derived.useRefsType,
        useCodeForOpRef: cgWFDataModelHooks.derived.useCodeForOpRef,
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
  // const { result: hasTSData } = useProjectHasTraceServerData(entityName, projectName);
  const hasTSData = true;

  if (hasTSData) {
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
  return (
    <WFDataModelFromComputeGraphProvider>
      {children}
    </WFDataModelFromComputeGraphProvider>
  );
};

/**
 * Returns true if the client can connect to trace server and the project has
 * calls.
 */
export const useProjectHasTraceServerCalls = (
  entity: string,
  project: string
) => {
  const hasTraceServer = useHasTraceServerClientContext();
  const calls = tsWFDataModelHooks.useCalls(entity, project, {}, 1, {
    skip: !hasTraceServer,
  });
  const loading = calls.loading;
  return {
    loading,
    result: (calls.result ?? []).length > 0,
  };
};

/**
 * Returns true if the client can connect to trace server and the project has
 * objects or calls.
 */
export const useProjectHasTraceServerData = (
  entity: string,
  project: string
) => {
  const hasTraceServer = useHasTraceServerClientContext();
  const objs = tsWFDataModelHooks.useRootObjectVersions(
    entity,
    project,
    {},
    1,
    {
      skip: !hasTraceServer,
    }
  );

  const calls = tsWFDataModelHooks.useCalls(entity, project, {}, 1, {
    skip: !hasTraceServer,
  });
  const loading = objs.loading || calls.loading;
  return {
    loading,
    result: (objs.result ?? []).length > 0 || (calls.result ?? []).length > 0,
  };
};
