/**
 * This file defines `tsWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing access to the Weaveflow data model
 * backed by the "Trace Server" engine.
 */

import {isSimpleTypeShape, union} from '@wandb/weave/core/model/helpers';
import * as _ from 'lodash';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import * as Types from '../../../../../../core/model/types';
import {useDeepMemo} from '../../../../../../hookUtils';
import {isWeaveObjectRef, parseRef} from '../../../../../../react';
import {
  callCache,
  objectVersionCache,
  opVersionCache,
  refDataCache,
} from './cache';
import {
  WANDB_ARTIFACT_REF_PREFIX,
  WEAVE_PRIVATE_PREFIX,
  WEAVE_REF_PREFIX,
} from './constants';
import * as traceServerClient from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {Query} from './traceServerClientInterface/query';
import * as traceServerTypes from './traceServerClientTypes';
import {useClientSideCallRefExpansion} from './tsDataModelHooksCallRefExpansion';
import {refUriToObjectVersionKey, refUriToOpVersionKey} from './utilities';
import {
  CallFilter,
  CallKey,
  CallSchema,
  FeedbackKey,
  Loadable,
  LoadableWithError,
  ObjectVersionFilter,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpVersionFilter,
  OpVersionKey,
  OpVersionSchema,
  RawSpanFromStreamTableEra,
  Refetchable,
  RefMutation,
  TableQuery,
  WFDataModelHooksInterface,
} from './wfDataModelHooksInterface';

export const projectIdFromParts = ({
  entity,
  project,
}: {
  entity: string;
  project: string;
}) => `${entity}/${project}`;

// Trace server client keys that are promises
type TraceServerClientPromiseKeys = {
  [K in keyof traceServerClient.TraceServerClient]: traceServerClient.TraceServerClient[K] extends (
    ...args: any
  ) => Promise<any>
    ? K extends 'onCallDelete'
      ? never
      : K
    : never;
}[keyof traceServerClient.TraceServerClient];

const makeTraceServerEndpointHook = <
  FN extends TraceServerClientPromiseKeys,
  Input extends any[],
  Output
>(
  traceServerFnName: FN,
  preprocessFn: (...input: Input) => {
    params: Parameters<traceServerClient.TraceServerClient[FN]>[0];
    skip?: boolean;
  },
  postprocessFn: (
    res: Awaited<ReturnType<traceServerClient.TraceServerClient[FN]>>,
    ...input: Input
  ) => Output
) => {
  const useTraceServerRequest = (
    ...input: Input
  ): LoadableWithError<Output> => {
    input = useDeepMemo(input);
    const loadingInputRef = useRef<Input | null>(null);
    const getTsClient = useGetTraceServerClientContext();
    const [state, setState] = useState<LoadableWithError<Output>>({
      loading: true,
      result: null,
      error: null,
    });

    useEffect(() => {
      loadingInputRef.current = input;
      setState({loading: true, result: null, error: null});
      const req = preprocessFn(...input);
      if (req.skip) {
        setState({loading: false, result: null, error: null});
        return;
      }
      const client = getTsClient();
      client[traceServerFnName](req.params as any)
        .then(res => {
          if (input !== loadingInputRef.current) {
            return;
          }
          const output = postprocessFn(res as any, ...input);
          setState({loading: false, result: output, error: null});
        })
        .catch(err => {
          if (input !== loadingInputRef.current) {
            return;
          }
          setState({loading: false, result: null, error: err});
        });
    }, [getTsClient, input]);

    const loadingReturn = useMemo(
      () => ({loading: true, result: null, error: null}),
      []
    );
    if (loadingInputRef.current !== input) {
      return loadingReturn;
    }
    return state;
  };
  return useTraceServerRequest;
};

const useMakeTraceServerEndpoint = <
  FN extends TraceServerClientPromiseKeys,
  Input extends any[],
  Output
>(
  traceServerFnName: FN,
  preprocessFn: (
    ...input: Input
  ) => Parameters<traceServerClient.TraceServerClient[FN]>[0],
  postprocessFn: (
    res: Awaited<ReturnType<traceServerClient.TraceServerClient[FN]>>
  ) => Output
) => {
  const getTsClient = useGetTraceServerClientContext();
  const client = getTsClient();
  const traceServerRequest = useCallback(
    (...input: Input): Promise<Output> => {
      return client[traceServerFnName](preprocessFn(...input) as any).then(
        res => {
          return postprocessFn(res as any);
        }
      );
    },
    [client, postprocessFn, preprocessFn, traceServerFnName]
  );
  return traceServerRequest;
};

const useCall = (key: CallKey | null): Loadable<CallSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const cachedCall = key ? callCache.get(key) : null;
  const [callRes, setCallRes] =
    useState<traceServerTypes.TraceCallReadRes | null>(null);
  const deepKey = useDeepMemo(key);
  const doFetch = useCallback(() => {
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

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    return getTsClient().registerOnRenameListener(doFetch);
  }, [getTsClient, doFetch]);

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
    const result =
      callRes && 'call' in callRes && callRes.call
        ? traceCallToUICallSchema(callRes.call)
        : null;
    if (callRes == null || loadingRef.current) {
      return {
        loading: true,
        result: null,
      };
    } else if (result?.callId === key?.callId) {
      if (result) {
        callCache.set(key, result);
      }
      return {
        loading: false,
        result,
      };
    } else {
      // Stale call result
      return {
        loading: false,
        result: null,
      };
    }
  }, [cachedCall, callRes, key]);
};

const useCallsNoExpansion = (
  entity: string,
  project: string,
  filter: CallFilter,
  limit?: number,
  offset?: number,
  sortBy?: traceServerTypes.SortBy[],
  query?: Query,
  opts?: {skip?: boolean; refetchOnDelete?: boolean}
): Loadable<CallSchema[]> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [callRes, setCallRes] =
    useState<traceServerTypes.TraceCallsQueryRes | null>(null);
  const deepFilter = useDeepMemo(filter);

  const doFetch = useCallback(() => {
    if (opts?.skip) {
      return;
    }
    setCallRes(null);
    loadingRef.current = true;
    const req: traceServerTypes.TraceCallsQueryReq = {
      project_id: projectIdFromParts({entity, project}),
      filter: {
        op_names: deepFilter.opVersionRefs,
        input_refs: deepFilter.inputObjectVersionRefs,
        output_refs: deepFilter.outputObjectVersionRefs,
        parent_ids: deepFilter.parentIds,
        trace_ids: deepFilter.traceId ? [deepFilter.traceId] : undefined,
        call_ids: deepFilter.callIds,
        trace_roots_only: deepFilter.traceRootsOnly,
        wb_run_ids: deepFilter.runIds,
        wb_user_ids: deepFilter.userIds,
      },
      limit,
      offset,
      sort_by: sortBy,
      query,
    };
    const onSuccess = (res: traceServerTypes.TraceCallsQueryRes) => {
      loadingRef.current = false;
      setCallRes(res);
    };
    const onError = (e: any) => {
      loadingRef.current = false;
      console.error(e);
      setCallRes({calls: []});
    };
    getTsClient().callsStreamQuery(req).then(onSuccess).catch(onError);
  }, [
    entity,
    project,
    deepFilter,
    limit,
    opts?.skip,
    getTsClient,
    offset,
    sortBy,
    query,
  ]);

  // register doFetch as a callback after deletion
  useEffect(() => {
    if (opts?.refetchOnDelete) {
      const client = getTsClient();
      const unregisterDelete = client.registerOnDeleteListener(doFetch);
      const unregisterRename = client.registerOnRenameListener(doFetch);
      return () => {
        unregisterDelete();
        unregisterRename();
      };
    }
    return () => {};
  }, [opts?.refetchOnDelete, getTsClient, doFetch]);

  useEffect(() => {
    if (opts?.skip) {
      return;
    }
    doFetch();
  }, [opts?.skip, doFetch]);

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
        result: [],
      };
    }
    const allResults = (callRes?.calls ?? [])
      .filter(isValidTraceCall)
      .map(traceCallToUICallSchema);
    const result = allResults;

    if (callRes == null || loadingRef.current) {
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
  }, [callRes, entity, project, opts?.skip]);
};

const useCalls = (
  entity: string,
  project: string,
  filter: CallFilter,
  limit?: number,
  offset?: number,
  sortBy?: traceServerTypes.SortBy[],
  query?: Query,
  expandedRefColumns?: Set<string>,
  opts?: {skip?: boolean; refetchOnDelete?: boolean}
): Loadable<CallSchema[]> => {
  const calls = useCallsNoExpansion(
    entity,
    project,
    filter,
    limit,
    offset,
    sortBy,
    query,
    opts
  );

  // This is a temporary solution until the trace server supports
  // backend expansions of refs. We should expect to see this go away, and
  // this entire function replaced with the contents of `useCallsNoExpansion`.
  const {expandedCalls, isExpanding} = useClientSideCallRefExpansion(
    calls,
    expandedRefColumns
  );

  const loading = calls.loading || isExpanding;
  return useMemo(() => {
    return {
      loading,
      result: loading ? [] : expandedCalls.map(traceCallToUICallSchema),
    };
  }, [expandedCalls, loading]);
};

const useCallsStats = (
  entity: string,
  project: string,
  filter: CallFilter,
  query?: Query,
  opts?: {skip?: boolean; refetchOnDelete?: boolean}
) => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [callStatsRes, setCallStatsRes] =
    useState<LoadableWithError<traceServerTypes.TraceCallsQueryStatsRes> | null>(
      null
    );
  const deepFilter = useDeepMemo(filter);

  const doFetch = useCallback(() => {
    if (opts?.skip) {
      setCallStatsRes({loading: false, result: null, error: null});
      return;
    }
    loadingRef.current = true;
    setCallStatsRes(null);

    const req: traceServerTypes.TraceCallsQueryStatsReq = {
      project_id: projectIdFromParts({entity, project}),
      filter: {
        op_names: deepFilter.opVersionRefs,
        input_refs: deepFilter.inputObjectVersionRefs,
        output_refs: deepFilter.outputObjectVersionRefs,
        parent_ids: deepFilter.parentIds,
        trace_ids: deepFilter.traceId ? [deepFilter.traceId] : undefined,
        call_ids: deepFilter.callIds,
        trace_roots_only: deepFilter.traceRootsOnly,
        wb_run_ids: deepFilter.runIds,
        wb_user_ids: deepFilter.userIds,
      },
      query,
    };

    getTsClient()
      .callsQueryStats(req)
      .then(res => {
        loadingRef.current = false;
        setCallStatsRes({loading: false, result: res, error: null});
      })
      .catch(err => {
        loadingRef.current = false;
        setCallStatsRes({loading: false, result: null, error: err});
      });
  }, [deepFilter, entity, project, query, opts?.skip, getTsClient]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    if (!opts?.refetchOnDelete) {
      return;
    }
    return getTsClient().registerOnDeleteListener(doFetch);
  }, [getTsClient, doFetch, opts?.refetchOnDelete]);

  return useMemo(() => {
    if (opts?.skip) {
      return {loading: false, result: null, error: null};
    } else {
      if (callStatsRes == null || loadingRef.current) {
        return {loading: true, result: null, error: null};
      }
      return callStatsRes;
    }
  }, [callStatsRes, opts?.skip]);
};

const useCallsDeleteFunc = () => {
  const getTsClient = useGetTraceServerClientContext();

  const callsDelete = useCallback(
    (entity: string, project: string, callIDs: string[]): Promise<void> => {
      return getTsClient()
        .callsDelete({
          project_id: projectIdFromParts({entity, project}),
          call_ids: callIDs,
        })
        .then(() => {
          callIDs.forEach(callId => {
            callCache.del({
              entity,
              project,
              callId,
            });
          });
        });
    },
    [getTsClient]
  );

  return callsDelete;
};

const useCallUpdateFunc = () => {
  const getTsClient = useGetTraceServerClientContext();

  const callUpdate = useCallback(
    (
      entity: string,
      project: string,
      callID: string,
      newName: string
    ): Promise<void> => {
      return getTsClient()
        .callUpdate({
          project_id: projectIdFromParts({entity, project}),
          call_id: callID,
          display_name: newName,
        })
        .then(() => {
          callCache.del({
            entity,
            project,
            callId: callID,
          });
        });
    },
    [getTsClient]
  );

  return callUpdate;
};

const useCallsExport = () => {
  const getTsClient = useGetTraceServerClientContext();

  const downloadCallsExport = useCallback(
    (
      entity: string,
      project: string,
      contentType: traceServerTypes.ContentType,
      filter: CallFilter,
      limit?: number,
      offset?: number,
      sortBy?: traceServerTypes.SortBy[],
      query?: Query,
      expandedRefCols?: string[]
    ) => {
      const req: traceServerTypes.TraceCallsQueryReq = {
        project_id: projectIdFromParts({entity, project}),
        filter: {
          op_names: filter.opVersionRefs,
          input_refs: filter.inputObjectVersionRefs,
          output_refs: filter.outputObjectVersionRefs,
          parent_ids: filter.parentIds,
          trace_ids: filter.traceId ? [filter.traceId] : undefined,
          call_ids: filter.callIds,
          trace_roots_only: filter.traceRootsOnly,
          wb_run_ids: filter.runIds,
          wb_user_ids: filter.userIds,
        },
        limit,
        offset,
        sort_by: sortBy,
        query,
        columns: expandedRefCols ?? undefined,
      };
      return getTsClient().callsStreamDownload(req, contentType);
    },
    [getTsClient]
  );

  return downloadCallsExport;
};

const useFeedback = (
  key: FeedbackKey | null,
  sortBy?: traceServerTypes.SortBy[]
): LoadableWithError<traceServerTypes.Feedback[]> & Refetchable => {
  const getTsClient = useGetTraceServerClientContext();

  const [result, setResult] = useState<
    LoadableWithError<traceServerTypes.Feedback[]>
  >({
    loading: false,
    result: null,
    error: null,
  });
  const [doReload, setDoReload] = useState(false);
  const refetch = useCallback(() => {
    setDoReload(true);
  }, [setDoReload]);

  const deepKey = useDeepMemo(key);

  useEffect(() => {
    let mounted = true;
    if (doReload) {
      setDoReload(false);
    }
    if (!deepKey) {
      return;
    }
    setResult({loading: true, result: null, error: null});
    getTsClient()
      .feedbackQuery({
        project_id: projectIdFromParts({
          entity: deepKey.entity,
          project: deepKey.project,
        }),
        query: {
          $expr: {
            $eq: [{$getField: 'weave_ref'}, {$literal: deepKey.weaveRef}],
          },
        },
        sort_by: sortBy ?? [{field: 'created_at', direction: 'desc'}],
      })
      .then(res => {
        if (!mounted) {
          return;
        }
        if ('result' in res) {
          setResult({loading: false, result: res.result, error: null});
        }
        // TODO: handle error case
      })
      .catch(err => {
        if (!mounted) {
          return;
        }
        setResult({loading: false, result: null, error: err});
      });
    return () => {
      mounted = false;
    };
  }, [deepKey, getTsClient, doReload, sortBy]);

  return {...result, refetch};
};

const useOpVersion = (
  // Null value skips
  key: OpVersionKey | null
): Loadable<OpVersionSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const cachedOpVersion = key ? opVersionCache.get(key) : null;
  const [opVersionRes, setOpVersionRes] =
    useState<traceServerTypes.TraceObjReadRes | null>(null);
  const deepKey = useDeepMemo(key);
  useEffect(() => {
    if (deepKey) {
      setOpVersionRes(null);
      loadingRef.current = true;
      getTsClient()
        .objRead({
          project_id: projectIdFromParts({
            entity: deepKey?.entity ?? '',
            project: deepKey?.project ?? '',
          }),
          object_id: deepKey?.opId ?? '',
          digest: deepKey?.versionHash ?? '',
        })
        .then(res => {
          loadingRef.current = false;
          setOpVersionRes(res);
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
    if (cachedOpVersion != null) {
      return {
        loading: false,
        result: cachedOpVersion,
      };
    }
    if (opVersionRes == null || loadingRef.current) {
      return {
        loading: true,
        result: null,
      };
    }

    if (opVersionRes.obj == null) {
      return {
        loading: false,
        result: null,
      };
    }

    const returnedResult = convertTraceServerObjectVersionToOpSchema(
      opVersionRes.obj
    );

    if (
      key.entity !== returnedResult.entity ||
      key.project !== returnedResult.project ||
      key.opId !== returnedResult.opId ||
      key.versionHash !== returnedResult.versionHash
    ) {
      return {
        loading: true,
        result: null,
      };
    }

    const cacheableResult: OpVersionSchema = {
      ...key,
      ...returnedResult,
    };

    opVersionCache.set(key, cacheableResult);
    return {
      loading: false,
      result: cacheableResult,
    };
  }, [cachedOpVersion, key, opVersionRes]);
};

const convertTraceServerObjectVersionToOpSchema = (
  obj: traceServerTypes.TraceObjSchema
): OpVersionSchema => {
  const [entity, project] = obj.project_id.split('/');
  return {
    entity,
    project,
    opId: obj.object_id,
    versionHash: obj.digest,
    createdAtMs: convertISOToDate(obj.created_at).getTime(),
    versionIndex: obj.version_index,
  };
};

const useOpVersions = makeTraceServerEndpointHook<
  'objsQuery',
  [string, string, OpVersionFilter, number?, {skip?: boolean}?],
  OpVersionSchema[]
>(
  'objsQuery',
  (
    entity: string,
    project: string,
    filter: OpVersionFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => ({
    params: {
      project_id: projectIdFromParts({entity, project}),
      // entity,
      // project,
      filter: {
        object_ids: filter.opIds,
        latest_only: filter.latestOnly,
        is_op: true,
      },
    },
    skip: opts?.skip,
  }),
  (res): OpVersionSchema[] =>
    res.objs.map(convertTraceServerObjectVersionToOpSchema)
);

const useFileContent = makeTraceServerEndpointHook<
  'fileContent',
  [string, string, string, {skip?: boolean}?],
  ArrayBuffer
>(
  'fileContent',
  (
    entity: string,
    project: string,
    digest: string,
    opts?: {skip?: boolean}
  ) => ({
    params: {
      project_id: projectIdFromParts({entity, project}),
      digest,
    },
    skip: opts?.skip,
  }),
  res => res.content
);

const useObjectVersion = (
  // Null value skips
  key: ObjectVersionKey | null
): Loadable<ObjectVersionSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const cachedObjectVersion = key ? objectVersionCache.get(key) : null;
  const [objectVersionRes, setObjectVersionRes] =
    useState<traceServerTypes.TraceObjReadRes | null>(null);
  const deepKey = useDeepMemo(key);
  useEffect(() => {
    if (deepKey) {
      setObjectVersionRes(null);
      loadingRef.current = true;
      getTsClient()
        .objRead({
          project_id: projectIdFromParts({
            entity: deepKey?.entity ?? '',
            project: deepKey?.project ?? '',
          }),
          object_id: deepKey?.objectId ?? '',
          digest: deepKey?.versionHash ?? '',
        })
        .then(res => {
          loadingRef.current = false;
          setObjectVersionRes(res);
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
    if (cachedObjectVersion != null) {
      return {
        loading: false,
        result: cachedObjectVersion,
      };
    }
    if (objectVersionRes == null || loadingRef.current) {
      return {
        loading: true,
        result: null,
      };
    }

    if (objectVersionRes.obj == null) {
      return {
        loading: false,
        result: null,
      };
    }

    const returnedResult: ObjectVersionSchema =
      convertTraceServerObjectVersionToSchema(objectVersionRes.obj);

    if (
      key.entity !== returnedResult.entity ||
      key.project !== returnedResult.project ||
      key.objectId !== returnedResult.objectId ||
      key.versionHash !== returnedResult.versionHash
    ) {
      return {
        loading: true,
        result: null,
      };
    }

    const cacheableResult: ObjectVersionSchema = {
      ...key,
      ...returnedResult,
    };

    objectVersionCache.set(key, cacheableResult);
    return {
      loading: false,
      result: cacheableResult,
    };
  }, [cachedObjectVersion, key, objectVersionRes]);
};

const convertTraceServerObjectVersionToSchema = (
  obj: traceServerTypes.TraceObjSchema
): ObjectVersionSchema => {
  const [entity, project] = obj.project_id.split('/');
  return {
    scheme: 'weave' as const,
    entity,
    project,
    weaveKind: 'object' as const,
    objectId: obj.object_id,
    versionHash: obj.digest,
    path: 'obj',
    createdAtMs: convertISOToDate(obj.created_at).getTime(),
    baseObjectClass: obj.base_object_class ?? null,
    versionIndex: obj.version_index,
    val: obj.val,
  };
};

const useRootObjectVersions = makeTraceServerEndpointHook(
  'objsQuery',
  (
    entity: string,
    project: string,
    filter: ObjectVersionFilter,
    limit?: number,
    opts?: {skip?: boolean}
  ) => ({
    params: {
      project_id: projectIdFromParts({entity, project}),
      filter: {
        base_object_classes: filter.baseObjectClasses,
        object_ids: filter.objectIds,
        latest_only: filter.latestOnly,
        is_op: false,
      },
    },
    skip: opts?.skip,
  }),
  (
    res,
    inputEntity,
    inputProject,
    filter,
    limit,
    opts
  ): ObjectVersionSchema[] =>
    res.objs.map(convertTraceServerObjectVersionToSchema)
);

const useRefsReadBatch = makeTraceServerEndpointHook<
  'readBatch',
  [string[], {skip?: boolean}?],
  any[]
>(
  'readBatch',
  (refs: string[], opts?: {skip?: boolean}) => ({
    params: {
      refs,
    },
    skip: opts?.skip,
  }),
  res => res.vals
);

const useTableQuery = makeTraceServerEndpointHook<
  'tableQuery',
  [
    string,
    string,
    traceServerTypes.TraceTableQueryReq['filter'],
    traceServerTypes.TraceTableQueryReq['limit'],
    {skip?: boolean}?
  ],
  any[]
>(
  'tableQuery',
  (
    projectId: traceServerTypes.TraceTableQueryReq['project_id'],
    digest: traceServerTypes.TraceTableQueryReq['digest'],
    filter: traceServerTypes.TraceTableQueryReq['filter'],
    limit: traceServerTypes.TraceTableQueryReq['limit'],
    opts?: {skip?: boolean}
  ) => ({
    params: {
      project_id: projectId,
      digest,
      filter,
      limit,
    },
    skip: opts?.skip,
  }),
  res => res.rows
);

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
    undefined,
    undefined,
    undefined,
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
    undefined,
    undefined,
    undefined,
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
  const refUrisDeep = useDeepMemo(refUris);

  const [nonTableRefUris, tableRefUris] = useMemo(() => {
    const sUris: string[] = [];
    const tUris: string[] = [];
    refUrisDeep
      .map(uri => ({uri, ref: refUriToObjectVersionKey(uri)}))
      .forEach(({uri, ref}, ndx) => {
        if (ref.scheme === 'weave' && ref.weaveKind === 'table') {
          tUris.push(uri);
        } else {
          sUris.push(uri);
        }
      });
    return [sUris, tUris];
  }, [refUrisDeep]);

  const [neededSimpleUris, cachedSimpleUriResults] = useMemo(() => {
    const needed: string[] = [];
    const cached: Record<string, any> = {};
    nonTableRefUris.forEach(sUri => {
      const res = refDataCache.get(sUri);
      if (res == null) {
        needed.push(sUri);
      } else {
        cached[sUri] = res;
      }
    });
    return [needed, cached];
  }, [nonTableRefUris]);

  const simpleValsResult = useRefsReadBatch(neededSimpleUris, {
    skip: neededSimpleUris.length === 0,
  });
  let tableUriProjectId = '';
  let tableUriDigest = '';
  if (tableRefUris.length > 1) {
    throw new Error('Multiple table refs not supported');
  } else if (tableRefUris.length === 1) {
    const tableRef = refUriToObjectVersionKey(tableRefUris[0]);
    tableUriProjectId = tableRef.entity + '/' + tableRef.project;
    tableUriDigest = tableRef.objectId;
  }
  const tableQueryFilter = useMemo(() => {
    // TODO: tableQuery
    return {};
  }, []);

  const tableRefKey = useMemo(() => {
    return (
      tableRefUris[0] +
      JSON.stringify(tableQueryFilter) +
      tableQuery?.limit?.toString()
    );
  }, [tableQuery?.limit, tableQueryFilter, tableRefUris]);

  const cachedTableResult = refDataCache.get(tableRefKey);

  const tableValsResult = useTableQuery(
    tableUriProjectId,
    tableUriDigest,
    tableQueryFilter,
    tableQuery?.limit,
    {skip: tableRefUris.length === 0 || cachedTableResult != null}
  );

  return useMemo(() => {
    if (refUris.length === 0) {
      return {
        loading: false,
        result: [],
        error: null,
      };
    }
    if (simpleValsResult.loading || tableValsResult.loading) {
      return {
        loading: true,
        result: null,
        error: null,
      };
    }
    const sRes = simpleValsResult.result;
    const tRes = cachedTableResult || tableValsResult.result;

    const valueMap = new Map<string, any>();
    if (sRes != null) {
      sRes.forEach((val, i) => {
        valueMap.set(neededSimpleUris[i], val);
        refDataCache.set(neededSimpleUris[i], val);
      });
    }
    if (tRes != null) {
      valueMap.set(tableRefUris[0], tRes);
      refDataCache.set(tableRefKey, tRes);
    }
    Object.entries(cachedSimpleUriResults).forEach(([uri, val]) => {
      valueMap.set(uri, val);
    });
    const valsResult = refUris.map(uri => valueMap.get(uri));

    return {
      loading: false,
      result: valsResult,
      error: null,
    };
  }, [
    refUris,
    simpleValsResult.loading,
    simpleValsResult.result,
    tableValsResult.loading,
    tableValsResult.result,
    cachedTableResult,
    cachedSimpleUriResults,
    neededSimpleUris,
    tableRefUris,
    tableRefKey,
  ]);
};

const useApplyMutationsToRef = (): ((
  refUri: string,
  edits: RefMutation[]
) => Promise<string>) => {
  throw new Error('Not implemented');
};

const useGetRefsType = (): ((refUris: string[]) => Promise<Types.Type[]>) => {
  const readBatch = useMakeTraceServerEndpoint(
    'readBatch',
    (refs: string[]) => ({
      refs,
    }),
    (res): any[] => res.vals
  );
  return async (refUris: string[]) => {
    if (refUris.length === 0) {
      return [];
    }
    const needed: string[] = [];
    const refToData: Record<string, any> = {};
    refUris.forEach(uri => {
      const res = refDataCache.get(uri);
      if (res == null) {
        needed.push(uri);
      } else {
        refToData[uri] = res;
      }
    });
    if (needed.length !== 0) {
      const readBatchResults = await readBatch(refUris);
      readBatchResults.forEach((res, i) => {
        refToData[needed[i]] = res;
        refDataCache.set(needed[i], res);
      });
    }
    return refUris.map(uri => weaveTypeOf(refToData[uri]));
  };
};

const useCodeForOpRef = (opVersionRef: string): Loadable<string> => {
  const query = useRefsData([opVersionRef]);
  const fileSpec = useMemo(() => {
    if (query.result == null) {
      return null;
    }
    const result = query.result[0];
    if (result == null) {
      return null;
    }
    const ref = parseRef(opVersionRef);
    if (isWeaveObjectRef(ref)) {
      return {
        digest: result.files['obj.py'],
        entity: ref.entityName,
        project: ref.projectName,
      };
    }
    return null;
  }, [opVersionRef, query.result]);
  const arrayBuffer = useFileContent(
    fileSpec?.entity ?? '',
    fileSpec?.project ?? '',
    fileSpec?.digest ?? '',
    {skip: fileSpec == null}
  );
  const text = useMemo(() => {
    if (arrayBuffer.loading || query.loading) {
      return {
        loading: true,
        result: null,
      };
    }
    return {
      loading: false,
      result: arrayBuffer.result
        ? new TextDecoder().decode(arrayBuffer.result)
        : null,
    };
  }, [arrayBuffer.loading, arrayBuffer.result, query.loading]);

  return text;
};

const mergeTypes = (a: Types.Type, b: Types.Type): Types.Type => {
  // TODO: this should match the python merge_types implementation.
  if (_.isEqual(a, b)) {
    return a;
  }
  if (isSimpleTypeShape(a) && isSimpleTypeShape(b)) {
    if (a === b) {
      return a;
    } else {
      return union([a, b]);
    }
  }
  if (!isSimpleTypeShape(a) && !isSimpleTypeShape(b)) {
    if (a.type === 'typedDict' && b.type === 'typedDict') {
      const allKeysDict = Object.assign({}, a.propertyTypes, b.propertyTypes);
      const nextPropTypes = _.mapValues(allKeysDict, (value, key) => {
        const selfPropType = a.propertyTypes[key] ?? 'none';
        const otherPropType = b.propertyTypes[key] ?? 'none';
        return mergeTypes(selfPropType, otherPropType);
      });
      return {
        type: 'typedDict',
        propertyTypes: nextPropTypes,
      };
    } else if (a.type === 'list' && b.type === 'list') {
      return {
        type: 'list',
        objectType: mergeTypes(a.objectType, b.objectType),
      };
    } else {
      // This gets very noisy, so commenting out for now.
      // console.warn('unhandled type merge ' + a.type + ' ' + b.type);
    }
  }
  return union([a, b]);
};

const mergeAllTypes = (types: Types.Type[]): Types.Type => {
  return types.reduce(mergeTypes);
};

const weaveTypeOf = (o: any): Types.Type => {
  if (o == null) {
    return 'none';
  } else if (_.isArray(o)) {
    return {
      type: 'list',
      objectType:
        o.length === 0 ? 'unknown' : mergeAllTypes(o.map(weaveTypeOf)),
    };
  } else if (_.isObject(o)) {
    if ('_type' in o) {
      return {
        type: (o as any)._type,
        _base_type: {type: 'Object'},
        _is_object: true,
        ..._.mapValues(_.omit(o, ['_type']), weaveTypeOf),
      } as any;
    } else {
      return {
        type: 'typedDict',
        propertyTypes: _.mapValues(o, weaveTypeOf),
      } as any;
    }
  } else if (_.isString(o)) {
    if (o.startsWith(WANDB_ARTIFACT_REF_PREFIX)) {
      return {
        type: 'WandbArtifactRef',
      };
    } else if (o.startsWith(WEAVE_REF_PREFIX)) {
      return {type: 'Ref'};
    }
    return 'string';
  } else if (_.isNumber(o)) {
    return 'number'; // TODO
  } else if (_.isBoolean(o)) {
    return 'boolean';
  }
  throw new Error('Type conversion not implemented for value: ' + o);
};

const useRefsType = (refUris: string[]): Loadable<Types.Type[]> => {
  const dataResult = useRefsData(refUris);
  const finalRes = useMemo(() => {
    if (!dataResult.loading) {
      return {
        loading: false,
        result: dataResult.result?.map(weaveTypeOf) ?? [],
        error: null,
      };
    } else {
      return {
        loading: true,
        result: null,
        error: null,
      };
    }
  }, [dataResult.loading, dataResult.result]);
  return finalRes;
};

/// Converters ///
type StatusCodeType = 'SUCCESS' | 'ERROR' | 'UNSET';
export const traceCallStatusCode = (
  traceCall: traceServerTypes.TraceCallSchema
): StatusCodeType => {
  if (traceCall.exception) {
    return 'ERROR';
  } else if (traceCall.ended_at) {
    return 'SUCCESS';
  } else {
    return 'UNSET';
  }
};

export const traceCallLatencyS = (
  traceCall: traceServerTypes.TraceCallSchema
) => {
  const startDate = convertISOToDate(traceCall.started_at);
  const endDate = traceCall.ended_at
    ? convertISOToDate(traceCall.ended_at)
    : null;
  let latencyS = 0;
  if (startDate && endDate) {
    latencyS = (endDate.getTime() - startDate.getTime()) / 1000;
  }
  return latencyS;
};

const traceCallToLegacySpan = (
  traceCall: traceServerTypes.TraceCallSchema
): RawSpanFromStreamTableEra => {
  const startDate = convertISOToDate(traceCall.started_at);
  const endDate = traceCall.ended_at
    ? convertISOToDate(traceCall.ended_at)
    : null;
  const summary = {
    latency_s: traceCallLatencyS(traceCall),
    ...(traceCall.summary ?? {}),
  };

  // This is a very specific hack to make sure that the output is always an
  // object. After the clickhouse migration, we no longer have this constraint.
  // Before, if the output was a simple type, it would be wrapped in an object
  // with the key '_result'. The rest of the codebase expects this, so we're
  // keeping it for now. However, this is causing some weirdness in the UI so we
  // should remove it soon. When we do that, we can also remove this hack.
  const unknownOutput = traceCall.output;
  let output: {[key: string]: any};
  if (
    typeof unknownOutput === 'object' &&
    unknownOutput !== null &&
    !Array.isArray(unknownOutput)
  ) {
    // If the output is already an object, we don't need to do anything.
    output = unknownOutput as {[key: string]: any};
  } else {
    // If the output is a simple type, we wrap it in an object with the key
    // '_result'.
    output = {_result: unknownOutput as any};
  }
  return {
    name: traceCall.op_name,
    inputs: traceCall.inputs,
    output,
    status_code: traceCallStatusCode(traceCall),
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

// Hack - underlying client should be updated to handle deleted projects better.
const isValidTraceCall = (callRes: traceServerTypes.TraceCallSchema) => {
  return !('detail' in callRes);
};

export const privateRefToSimpleName = (ref: string) => {
  const trimmed = ref.replace(`${WEAVE_PRIVATE_PREFIX}//`, '');
  try {
    return trimmed.split('/')[1].split(':')[0];
  } catch (e) {
    return trimmed;
  }
};

export const traceCallToUICallSchema = (
  traceCall: traceServerTypes.TraceCallSchema
): CallSchema => {
  const {entity, project} = projectIdToParts(traceCall.project_id);
  const parseSpanName = (opName: string) => {
    if (
      opName.startsWith(WANDB_ARTIFACT_REF_PREFIX) ||
      opName.startsWith(WEAVE_REF_PREFIX)
    ) {
      return refUriToOpVersionKey(opName).opId;
    }
    if (opName.startsWith(WEAVE_PRIVATE_PREFIX)) {
      return privateRefToSimpleName(opName);
    }
    return opName;
  };
  return {
    entity,
    project,
    callId: traceCall.id,
    traceId: traceCall.trace_id,
    parentId: traceCall.parent_id ?? null,
    spanName: parseSpanName(traceCall.op_name),
    displayName: traceCall.display_name ?? null,
    opVersionRef:
      traceCall.op_name.startsWith(WANDB_ARTIFACT_REF_PREFIX) ||
      traceCall.op_name.startsWith(WEAVE_REF_PREFIX) ||
      traceCall.op_name.startsWith(WEAVE_PRIVATE_PREFIX)
        ? traceCall.op_name
        : null,
    rawSpan: traceCallToLegacySpan(traceCall),
    rawFeedback: {},
    userId: traceCall.wb_user_id ?? null,
    runId: traceCall.wb_run_id ?? null,
    traceCall,
  };
};

/// Utility Functions ///

export const convertISOToDate = (iso: string): Date => {
  return new Date(iso);
};

// Export //

export const tsWFDataModelHooks: WFDataModelHooksInterface = {
  useCall,
  useCalls,
  useCallsStats,
  useCallsDeleteFunc,
  useCallUpdateFunc,
  useCallsExport,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useRootObjectVersions,
  useRefsData,
  useApplyMutationsToRef,
  useFeedback,
  useFileContent,
  derived: {
    useChildCallsForCompare,
    useGetRefsType,
    useRefsType,
    useCodeForOpRef,
  },
};
