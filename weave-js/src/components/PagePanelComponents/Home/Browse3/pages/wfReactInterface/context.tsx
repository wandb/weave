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

import {useWeaveContext} from '../../../../../../context';
import {BasicClient} from '../../../../../../core';
import {cgWFDataModelHooks} from './cgDataModelHooks';
import {placeholderWFDataModelHooks} from './placeholderDataModelHooks';
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

const WFDataModelPlaceholderProvider: FC = ({children}) => {
  return (
    <WFDataModelHooksContext.Provider value={placeholderWFDataModelHooks}>
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

  // Default to empty placeholder to not crash the app
  return (
    <WFDataModelPlaceholderProvider>{children}</WFDataModelPlaceholderProvider>
  );
};

/**
 * Returns true if the client can connect to compute graph execution engine and
 * the project has data in the compute graph.
 */
const useProjectHasCGData = (entity: string, project: string) => {
  const client = useWeaveContext();
  const connectedToCGServer = useMemo(
    () => client instanceof BasicClient && client.isRemoteServerClient(),
    [client]
  );
  const calls = cgWFDataModelHooks.useCalls(entity, project, {}, 1, {
    skip: !connectedToCGServer,
  });
  return (calls.result ?? []).length > 0;
};

/**
 * Returns true if the client can connect to trace server and the project has
 * data in the trace server.
 */
const useProjectHasTSData = (entity: string, project: string) => {
  const hasTraceServer = useHasTraceServerClientContext();
  const calls = tsWFDataModelHooks.useCalls(entity, project, {}, 1, {
    skip: !hasTraceServer,
  });
  return (calls.result ?? []).length > 0;
};

/**
 * Returns true if the project has data in either the compute graph or the trace
 * server.
 */
export const useProjectHasTraceData = (entity: string, project: string) => {
  const hasCG = useProjectHasCGData(entity, project);
  const hasTS = useProjectHasTSData(entity, project);
  return hasCG || hasTS;
};
