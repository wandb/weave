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
import {projectIdFromParts, tsWFDataModelHooks} from './tsDataModelHooks';
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
  const projectId = projectIdFromParts({entity, project});
  const hasCalls = tsWFDataModelHooks.useProjectCheck(projectId, {
    skip: !hasTraceServer,
  });
  const hasData = !!hasCalls.result?.has_data;
  return useMemo(
    () => ({
      loading: hasCalls.loading,
      result: hasData,
    }),
    [hasCalls.loading, hasData]
  );
};
