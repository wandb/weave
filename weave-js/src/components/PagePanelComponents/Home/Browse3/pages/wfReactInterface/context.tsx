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
      useRefsData: cgWFDataModelHooks.useRefsData,
      useApplyMutationsToRef: cgWFDataModelHooks.useApplyMutationsToRef,
      derived: {
        useChildCallsForCompare:
          tsWFDataModelHooks.derived.useChildCallsForCompare,
        useGetRefsType: cgWFDataModelHooks.derived.useGetRefsType,
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
  const hasTSData = useProjectHasTraceServerCalls(entityName, projectName);

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
 * data in the trace server.
 */
export const useProjectHasTraceServerCalls = (
  entity: string,
  project: string
) => {
  const hasTraceServer = useHasTraceServerClientContext();
  const calls = tsWFDataModelHooks.useCalls(entity, project, {}, 1, {
    skip: !hasTraceServer,
  });

  return (calls.result ?? []).length > 0;
};
