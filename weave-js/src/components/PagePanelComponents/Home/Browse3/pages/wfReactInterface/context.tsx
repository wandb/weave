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

import {useHasTraceServerClientContext} from './traceServerClientContext';
import {tsWFDataModelHooks} from './tsDataModelHooks';
import {WFDataModelHooksInterface} from './wfDataModelHooksInterface';

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

export const WFDataModelAutoProvider: FC<{
  entityName: string;
  projectName: string;
}> = ({entityName, projectName, children}) => {
  return (
    <WFDataModelHooksContext.Provider value={tsWFDataModelHooks}>
      {children}
    </WFDataModelHooksContext.Provider>
  );
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
    true,
    {
      skip: !hasTraceServer,
      noAutoRefresh: true,
    }
  );
  const columns = useMemo(() => ['id'], []);

  const calls = tsWFDataModelHooks.useCalls(
    entity,
    project,
    {},
    1,
    undefined,
    undefined,
    undefined,
    columns,
    undefined,
    {
      skip: !hasTraceServer,
    }
  );
  const loading = objs.loading || calls.loading;
  return useMemo(
    () => ({
      loading,
      result: (objs.result ?? []).length > 0 || (calls.result ?? []).length > 0,
    }),
    [loading, objs.result, calls.result]
  );
};
