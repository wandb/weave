/**
 * This file defines `tsWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing access to the Weaveflow data model
 * backed by the "Trace Server" engine.
 */

import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import * as Types from '../../../../../../core/model/types';
import {useDeepMemo} from '../../../../../../hookUtils';
import {callCache} from './cache';
import {WANDB_ARTIFACT_REF_PREFIX} from './constants';
import * as traceServerClient from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {opVersionRefOpCategory, refUriToOpVersionKey} from './utilities';
import {
  CallFilter,
  CallKey,
  CallSchema,
  Loadable,
  ObjectVersionFilter,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpCategory,
  OpVersionFilter,
  OpVersionKey,
  OpVersionSchema,
  RawSpanFromStreamTableEra,
  RefMutation,
  TableQuery,
  WFDataModelHooksInterface,
} from './wfDataModelHooksInterface';

const DEFAULT_PAGE_SIZE = 10000;
const DEFAULT_MAX_PAGES = 50;

const projectIdFromParts = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
}) => `${entity}/${project}`;

const useCall = (key: CallKey | null): Loadable<CallSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const cachedCall = key ? callCache.get(key) : null;
  const [callRes, setCallRes] =
    useState<traceServerClient.TraceCallReadRes | null>(null);
  const deepKey = useDeepMemo(key);
  useEffect(() => {
    if (deepKey) {
      setCallRes(null);
      loadingRef.current = true;
      getTsClient()
        .callRead({
          project_id: projectIdFromParts(deepKey),
          id: deepKey.callId,
        })
        .then(res => {
          loadingRef.current = false;
          setCallRes(res);
        });
    }
  }, [deepKey, getTsClient]);

  return useMemo(() => {
    if (key == null) {
      return {
        loading: false,
        result: null,
      };
    }
    if (cachedCall != null) {
      return {
        loading: false,
        result: cachedCall,
      };
    }
    const result = callRes ? traceCallToUICallSchema(callRes.call) : null;
    if (callRes == null || loadingRef.current) {
      return {
        loading: true,
        result: null,
      };
    } else {
      if (result) {
        callCache.set(key, result);
      }
      return {
        loading: false,
        result,
      };
    }
  }, [cachedCall, callRes, key]);
};

const useCalls = (
  entity: string,
  project: string,
  filter: CallFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<CallSchema[]> => {
  const getTsClient = useGetTraceServerClientContext();
  // if allCallsLoaded is true, we have loaded all calls, this is how we tell if we are loading
  // if skip is true, we don't need to load any calls
  const [allCallsLoaded, setAllCallsLoaded] = useState(opts?.skip ?? false);
  const [callRes, setCallRes] = useState<traceServerClient.TraceCallSchema[]>(
    []
  );
  const deepFilter = useDeepMemo(filter);

  // this is only used if the limit that is passed in is greater than the default page size
  const isLargeLimit = limit !== undefined && limit >= DEFAULT_PAGE_SIZE;
  const isSmallLimit = limit !== undefined && limit < DEFAULT_PAGE_SIZE;
  const callLimit = isLargeLimit
    ? limit
    : DEFAULT_PAGE_SIZE * DEFAULT_MAX_PAGES;

  // if a limit is provided and is less than 10,000, we use that and only return the single page
  // otherwise we use a default of 10,000 and load a max of 50 pages to return all calls
  // Arbitrary page limit of 10,000, in conjunction with the max 50 pages limits calls to 500,000
  const pageSize = isSmallLimit ? limit : DEFAULT_PAGE_SIZE;
  const maxPages = isSmallLimit ? 0 : DEFAULT_MAX_PAGES;

  // This is a recursive function that loads calls in pages from the trace server into an accumulator
  // This is a workaround for the trace server not being able to send super large pages over the wire
  const loadCalls = useCallback(
    async (
      pageNumber: number,
      acc: traceServerClient.TraceCallSchema[],
      leftoverCalls: number
    ) => {
      // opts.skip will set this true if passed in
      // if all calls are already loaded, we dont need to do anything
      if (allCallsLoaded) {
        return;
      }

      try {
        const res = await getTsClient().callsQuery({
          project_id: projectIdFromParts({entity, project}),
          filter: {
            op_version_refs: deepFilter.opVersionRefs,
            input_object_version_refs: deepFilter.inputObjectVersionRefs,
            output_object_version_refs: deepFilter.outputObjectVersionRefs,
            parent_ids: deepFilter.parentIds,
            trace_ids: deepFilter.traceId ? [deepFilter.traceId] : undefined,
            call_ids: deepFilter.callIds,
            trace_roots_only: deepFilter.traceRootsOnly,
            wb_run_ids: deepFilter.runIds,
            wb_user_ids: deepFilter.userIds,
          },
          limit: leftoverCalls < pageSize ? leftoverCalls : pageSize,
          offset: pageNumber * pageSize,
        });

        if (res.calls.length < pageSize || pageNumber >= maxPages) {
          // If we get less than the pageSize (ie we reached the end)
          // or we've fetched the max amount pages, we stop fetching (so we don't want to fetch forever)
          setAllCallsLoaded(true);
          setCallRes([...acc, ...res.calls]);
        } else {
          // Continue fetching the next page
          loadCalls(
            pageNumber + 1,
            [...acc, ...res.calls],
            leftoverCalls - pageSize
          );
        }
      } catch (e) {
        setAllCallsLoaded(true);
        console.error(e);
      }
    },
    [
      allCallsLoaded,
      deepFilter.callIds,
      deepFilter.inputObjectVersionRefs,
      deepFilter.opVersionRefs,
      deepFilter.outputObjectVersionRefs,
      deepFilter.parentIds,
      deepFilter.runIds,
      deepFilter.traceId,
      deepFilter.traceRootsOnly,
      deepFilter.userIds,
      entity,
      getTsClient,
      maxPages,
      pageSize,
      project,
    ]
  );

  // loads calls based on page size and page limit
  useEffect(() => {
    if (!allCallsLoaded && !opts?.skip) {
      loadCalls(0, [], callLimit);
    }
  }, [
    allCallsLoaded,
    callLimit,
    deepFilter,
    entity,
    getTsClient,
    limit,
    loadCalls,
    opts?.skip,
    project,
  ]);

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
        result: [],
      };
    }
    const allResults = (!allCallsLoaded ? [] : callRes).map(
      traceCallToUICallSchema
    );
    const result = allResults.filter((row: any) => {
      return (
        deepFilter.opCategory == null ||
        (row.opVersionRef &&
          deepFilter.opCategory.includes(
            opVersionRefOpCategory(row.opVersionRef) as OpCategory
          ))
      );
    });

    if (!allCallsLoaded) {
      return {
        loading: true,
        result: [],
      };
    } else {
      allResults.forEach(call => {
        callCache.set(
          {
            entity,
            project,
            callId: call.callId,
          },
          call
        );
      });
      return {
        loading: false,
        result,
      };
    }
  }, [
    allCallsLoaded,
    callRes,
    deepFilter.opCategory,
    entity,
    opts?.skip,
    project,
  ]);
};

const useOpVersion = (
  // Null value skips
  key: OpVersionKey | null
): Loadable<OpVersionSchema | null> => {
  throw new Error('Not implemented');
};

const useOpVersions = (
  entity: string,
  project: string,
  filter: OpVersionFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<OpVersionSchema[]> => {
  throw new Error('Not implemented');
};

const useObjectVersion = (
  // Null value skips
  key: ObjectVersionKey | null
): Loadable<ObjectVersionSchema | null> => {
  throw new Error('Not implemented');
};

const useRootObjectVersions = (
  entity: string,
  project: string,
  filter: ObjectVersionFilter,
  limit?: number,
  opts?: {skip?: boolean}
): Loadable<ObjectVersionSchema[]> => {
  throw new Error('Not implemented');
};

const useChildCallsForCompare = (
  entity: string,
  project: string,
  parentCallIds: string[] | undefined,
  selectedOpVersionRef: string | null,
  selectedObjectVersionRef: string | null
): {
  loading: boolean;
  result: CallSchema[];
} => {
  // This should be moved to the trace server soon. Doing in memory join for
  // feature completeness now.
  const skipParent =
    parentCallIds == null ||
    parentCallIds.length === 0 ||
    selectedObjectVersionRef == null;

  const parentCalls = useCalls(
    entity,
    project,
    {
      callIds: parentCallIds,
      inputObjectVersionRefs: selectedObjectVersionRef
        ? [selectedObjectVersionRef]
        : [],
    },
    undefined,
    {skip: skipParent}
  );

  const subParentCallIds = useMemo(() => {
    return (parentCalls.result ?? []).map(call => call.callId);
  }, [parentCalls.result]);

  const skipChild =
    subParentCallIds.length === 0 || selectedOpVersionRef == null;

  const childCalls = useCalls(
    entity,
    project,
    {
      parentIds: subParentCallIds,
      opVersionRefs: selectedOpVersionRef ? [selectedOpVersionRef] : [],
    },
    undefined,
    {skip: skipChild}
  );

  const result = useMemo(() => {
    const loading = parentCalls.loading || childCalls.loading;
    if (loading) {
      return {loading, result: []};
    }
    if (skipChild || skipParent) {
      return {loading: false, result: []};
    }

    return {loading: false, result: childCalls.result ?? []};
  }, [
    childCalls.loading,
    childCalls.result,
    parentCalls.loading,
    skipChild,
    skipParent,
  ]);

  return result;
};

const useRefsData = (
  refUris: string[],
  tableQuery?: TableQuery
): Loadable<any[]> => {
  throw new Error('Not implemented');
};

const useApplyMutationsToRef = (): ((
  refUri: string,
  edits: RefMutation[]
) => Promise<string>) => {
  throw new Error('Not implemented');
};

const useGetRefsType = (): ((refUris: string[]) => Promise<Types.Type[]>) => {
  throw new Error('Not implemented');
};

const useRefsType = (refUris: string[]): Loadable<Types.Type[]> => {
  throw new Error('Not implemented');
};

/// Converters ///

const traceCallToLegacySpan = (
  traceCall: traceServerClient.TraceCallSchema
): RawSpanFromStreamTableEra => {
  const startDate = convertISOToDate(traceCall.start_datetime);
  const endDate = traceCall.end_datetime
    ? convertISOToDate(traceCall.end_datetime)
    : null;
  let statusCode = 'UNSET';
  if (traceCall.exception) {
    statusCode = 'ERROR';
  } else if (traceCall.end_datetime) {
    statusCode = 'SUCCESS';
  }
  let latencyS = 0;
  if (startDate && endDate) {
    latencyS = (endDate.getTime() - startDate.getTime()) / 1000;
  }
  const summary = {
    latency_s: latencyS,
    ...(traceCall.summary ?? {}),
  };
  return {
    name: traceCall.name,
    inputs: traceCall.inputs,
    output: traceCall.outputs,
    status_code: statusCode,
    exception: traceCall.exception,
    attributes: traceCall.attributes,
    summary,
    span_id: traceCall.id,
    trace_id: traceCall.trace_id,
    parent_id: traceCall.parent_id,
    timestamp: startDate.getTime(),
    start_time_ms: startDate.getTime(),
    end_time_ms: endDate?.getTime(),
  };
};

const projectIdToParts = (projectId: string) => {
  const [entity, project] = projectId.split('/');
  return {entity, project};
};

const traceCallToUICallSchema = (
  traceCall: traceServerClient.TraceCallSchema
): CallSchema => {
  const {entity, project} = projectIdToParts(traceCall.project_id);
  return {
    entity,
    project,
    callId: traceCall.id,
    traceId: traceCall.trace_id,
    parentId: traceCall.parent_id ?? null,
    spanName: traceCall.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? refUriToOpVersionKey(traceCall.name).opId
      : traceCall.name,
    opVersionRef: traceCall.name.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      ? traceCall.name
      : null,
    rawSpan: traceCallToLegacySpan(traceCall),
    rawFeedback: {},
    userId: traceCall.wb_user_id ?? null,
    runId: traceCall.wb_run_id ?? null,
  };
};

/// Utility Functions ///

const convertISOToDate = (iso: string) => {
  return new Date(iso);
};

// Export //

export const tsWFDataModelHooks: WFDataModelHooksInterface = {
  useCall,
  useCalls,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useRootObjectVersions,
  useRefsData,
  useApplyMutationsToRef,
  derived: {
    useChildCallsForCompare,
    useGetRefsType,
    useRefsType,
  },
};
