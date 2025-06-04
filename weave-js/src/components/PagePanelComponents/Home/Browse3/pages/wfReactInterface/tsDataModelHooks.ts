/**
 * This file defines `tsWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing access to the Weaveflow data model
 * backed by the "Trace Server" engine.
 */

import {isSimpleTypeShape, union} from '@wandb/weave/core/model/helpers';
import * as _ from 'lodash';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import useAsync from 'react-use/lib/useAsync';

import * as Types from '../../../../../../core/model/types';
import {useDeepMemo} from '../../../../../../hookUtils';
import {
  isWeaveObjectRef,
  parseRef,
  refUri,
  WeaveObjectRef,
} from '../../../../../../react';
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
import * as traceServerTypes from './traceServerClientTypes';
import {useClientSideCallRefExpansion} from './tsDataModelHooksCallRefExpansion';
import {opVersionRefOpName, refUriToObjectVersionKey} from './utilities';
import {
  CallSchema,
  Loadable,
  LoadableWithError,
  ObjectDeleteAllVersionsParams,
  ObjectDeleteParams,
  ObjectVersionKey,
  ObjectVersionSchema,
  OpVersionDeleteAllVersionsParams,
  OpVersionDeleteParams,
  OpVersionKey,
  OpVersionSchema,
  RawSpanFromStreamTableEra,
  Refetchable,
  UseApplyMutationsToRefParams,
  UseCallParams,
  UseCallsDeleteParams,
  UseCallsExportParams,
  UseCallsParams,
  UseCallsStatsParams,
  UseCallUpdateParams,
  UseChildCallsForCompareParams,
  UseFeedbackParams,
  UseFileContentParams,
  UseGetRefsTypeParams,
  UseObjCreateParams,
  UseObjectVersionParams,
  UseOpVersionParams,
  UseOpVersionsParams,
  UseProjectHasCallsParams,
  UseRefsDataParams,
  UseRefsReadBatchParams,
  UseRootObjectVersionsParams,
  UseTableQueryParams,
  UseTableQueryStatsParams,
  UseTableRowsQueryParams,
  UseTableUpdateParams,
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
  Params extends object,
  Output
>(
  traceServerFnName: FN,
  preprocessFn: (params: Params) => {
    params: Parameters<traceServerClient.TraceServerClient[FN]>[0];
    skip?: boolean;
  },
  postprocessFn: (
    res: Awaited<ReturnType<traceServerClient.TraceServerClient[FN]>>,
    params: Params
  ) => Output
) => {
  const useTraceServerRequest = (params: Params): LoadableWithError<Output> => {
    params = useDeepMemo(params);
    const loadingInputRef = useRef<Params | null>(null);
    const getTsClient = useGetTraceServerClientContext();
    const [state, setState] = useState<LoadableWithError<Output>>({
      loading: true,
      result: null,
      error: null,
    });

    useEffect(() => {
      loadingInputRef.current = params;
      setState({loading: true, result: null, error: null});
      const req = preprocessFn(params);
      if (req.skip) {
        setState({loading: false, result: null, error: null});
        return;
      }
      const client = getTsClient();
      client[traceServerFnName](req.params as any)
        .then(res => {
          if (params !== loadingInputRef.current) {
            return;
          }
          const output = postprocessFn(res as any, params);
          setState({loading: false, result: output, error: null});
        })
        .catch(err => {
          if (params !== loadingInputRef.current) {
            return;
          }
          setState({loading: false, result: null, error: err});
        });
    }, [getTsClient, params]);

    const loadingReturn = useMemo(
      () => ({loading: true, result: null, error: null}),
      []
    );
    if (loadingInputRef.current !== params) {
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

const useCall = (params: UseCallParams): Loadable<CallSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);

  const effectiveKey = useMemo(() => {
    if (params.key == null) {
      return null;
    }
    return {
      ...params.key,
      withCosts: !!params.includeCosts,
      withTotalStorageSize: !!params.includeTotalStorageSize,
    };
  }, [params.key, params.includeCosts, params.includeTotalStorageSize]);
  const deepKey = useDeepMemo(effectiveKey);

  const cachedCall = deepKey ? callCache.get(deepKey) : null;

  const [callRes, setCallRes] =
    useState<traceServerTypes.TraceCallReadRes | null>(null);
  const doFetch = useCallback(
    ({invalidateCache = false}: {invalidateCache?: boolean} = {}) => {
      if (deepKey) {
        if (invalidateCache) {
          callCache.del(deepKey);
        }
        loadingRef.current = true;
        setCallRes(null);
        getTsClient()
          .callRead({
            project_id: projectIdFromParts(deepKey),
            id: deepKey.callId,
            include_costs: params.includeCosts,
            ...(params.includeTotalStorageSize
              ? {include_total_storage_size: true}
              : null),
          })
          .then(res => {
            loadingRef.current = false;
            setCallRes(res);
          });
      }
    },
    [deepKey, getTsClient, params.includeCosts, params.includeTotalStorageSize]
  );

  useEffect(() => {
    doFetch({invalidateCache: false});
  }, [doFetch]);

  useEffect(() => {
    if (params.refetchOnRename) {
      const client = getTsClient();
      const unregisterRename = client.registerOnRenameListener(() =>
        doFetch({invalidateCache: true})
      );
      return () => {
        unregisterRename();
      };
    }
    return undefined;
  }, [getTsClient, doFetch, deepKey, params.refetchOnRename]);

  return useMemo(() => {
    if (deepKey == null) {
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
    } else if (result == null) {
      return {
        loading: false,
        result: null,
      };
    } else if (result?.callId === deepKey?.callId) {
      if (result) {
        callCache.set(deepKey, result);
      }
      return {
        loading: false,
        result,
      };
    } else {
      // Stale call result
      return {
        loading: true,
        result: null,
      };
    }
  }, [cachedCall, callRes, deepKey]);
};

const useCallsNoExpansion = (
  params: UseCallsParams
): Loadable<CallSchema[]> & Refetchable => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [callRes, setCallRes] =
    useState<traceServerTypes.TraceCallsQueryRes | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const deepFilter = useDeepMemo(params.filter);

  const req = useMemo((): traceServerTypes.TraceCallsQueryReq => {
    return {
      project_id: projectIdFromParts({
        entity: params.entity,
        project: params.project,
      }),
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
      limit: params.limit,
      offset: params.offset,
      sort_by: params.sortBy,
      query: params.query,
      columns: params.columns,
      include_costs: params.includeCosts,
      include_feedback: params.includeFeedback,
      ...(params.includeTotalStorageSize
        ? {include_total_storage_size: true}
        : null),
    };
  }, [
    params.entity,
    params.project,
    deepFilter,
    params.limit,
    params.offset,
    params.sortBy,
    params.query,
    params.columns,
    params.includeCosts,
    params.includeFeedback,
    params.includeTotalStorageSize,
  ]);

  // Keep track of the request we're waiting for, so that we
  // can ignore requests that are superseded by more recent reqs
  const expectedRequestRef = useRef(req);

  const doFetch = useCallback(() => {
    setCallRes(null);
    loadingRef.current = true;
    expectedRequestRef.current = req;

    const onSuccess = (res: traceServerTypes.TraceCallsQueryRes) => {
      // Only update state if this response matches our current request
      if (_.isEqual(expectedRequestRef.current, req)) {
        loadingRef.current = false;
        setCallRes(res);
      }
    };
    const onError = (e: any) => {
      // Only update state if this response matches our current request
      if (_.isEqual(expectedRequestRef.current, req)) {
        loadingRef.current = false;
        console.error(e);
        setError(e);
        setCallRes({calls: []});
      }
    };
    getTsClient().callsStreamQuery(req).then(onSuccess).catch(onError);
  }, [getTsClient, req]);

  // register doFetch as a callback after deletion
  useEffect(() => {
    if (params.refetchOnDelete) {
      const client = getTsClient();
      const unregisterDelete = client.registerOnDeleteListener(doFetch);
      const unregisterRename = client.registerOnRenameListener(doFetch);
      return () => {
        unregisterDelete();
        unregisterRename();
      };
    }
    return () => {};
  }, [params.refetchOnDelete, getTsClient, doFetch]);

  useEffect(() => {
    if (params.skip) {
      return;
    }
    doFetch();
  }, [params.skip, doFetch]);

  const refetch = useCallback(() => {
    doFetch();
  }, [doFetch]);

  return useMemo(() => {
    if (params.skip) {
      return {
        loading: false,
        result: [],
        refetch,
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
        refetch,
      };
    } else {
      // Check if the query contained a column request. Only cache calls
      // if no columns were requested, only then are we guaranteed to get
      // all the call data
      if (!params.columns) {
        allResults.forEach(call => {
          callCache.set(
            {
              entity: params.entity,
              project: params.project,
              callId: call.callId,
            },
            call
          );
        });
      }
      return {
        loading: false,
        result,
        refetch,
        error,
      };
    }
  }, [
    params.skip,
    callRes,
    params.columns,
    refetch,
    params.entity,
    params.project,
    error,
  ]);
};

const useCalls = (
  params: UseCallsParams
): Loadable<CallSchema[]> & Refetchable => {
  const calls = useCallsNoExpansion(params);

  // This is a temporary solution until the trace server supports
  // backend expansions of refs. We should expect to see this go away, and
  // this entire function replaced with the contents of `useCallsNoExpansion`.
  const {expandedCalls, isExpanding} = useClientSideCallRefExpansion(
    calls,
    params.expandedRefColumns
  );

  const loading = calls.loading || isExpanding;
  return useMemo(() => {
    return {
      loading,
      result: loading ? [] : expandedCalls.map(traceCallToUICallSchema),
      refetch: calls.refetch,
      error: calls.error,
    };
  }, [calls.refetch, expandedCalls, loading, calls.error]);
};

const useCallsStats = (
  params: UseCallsStatsParams
): Loadable<traceServerTypes.TraceCallsQueryStatsRes> & Refetchable => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [callStatsRes, setCallStatsRes] =
    useState<LoadableWithError<traceServerTypes.TraceCallsQueryStatsRes> | null>(
      null
    );
  const deepFilter = useDeepMemo(params.filter);

  const doFetch = useCallback(() => {
    if (params.skip) {
      setCallStatsRes({loading: false, result: null, error: null});
      return;
    }
    loadingRef.current = true;
    setCallStatsRes(null);

    const req: traceServerTypes.TraceCallsQueryStatsReq = {
      project_id: projectIdFromParts({
        entity: params.entity,
        project: params.project,
      }),
      filter: deepFilter
        ? {
            op_names: deepFilter?.opVersionRefs,
            input_refs: deepFilter?.inputObjectVersionRefs,
            output_refs: deepFilter?.outputObjectVersionRefs,
            parent_ids: deepFilter?.parentIds,
            trace_ids: deepFilter?.traceId ? [deepFilter.traceId] : undefined,
            call_ids: deepFilter?.callIds,
            trace_roots_only: deepFilter?.traceRootsOnly,
            wb_run_ids: deepFilter?.runIds,
            wb_user_ids: deepFilter?.userIds,
          }
        : undefined,
      query: params.query,
      limit: params.limit,
      ...(!!params.includeTotalStorageSize
        ? {include_total_storage_size: true}
        : null),
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
  }, [
    params.skip,
    params.includeTotalStorageSize,
    params.entity,
    params.project,
    deepFilter,
    params.query,
    params.limit,
    getTsClient,
  ]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    if (!params.refetchOnDelete) {
      return;
    }
    return getTsClient().registerOnDeleteListener(doFetch);
  }, [getTsClient, doFetch, params.refetchOnDelete]);

  const refetch = useCallback(() => {
    doFetch();
  }, [doFetch]);

  return useMemo(() => {
    if (params.skip) {
      return {loading: false, result: null, error: null, refetch};
    } else {
      if (callStatsRes == null || loadingRef.current) {
        return {loading: true, result: null, error: null, refetch};
      }
      return {...callStatsRes, refetch};
    }
  }, [callStatsRes, params.skip, refetch]);
};

const useProjectHasCalls = (
  params: UseProjectHasCallsParams
): Loadable<boolean> => {
  const callsStats = useCallsStats({
    entity: params.entity,
    project: params.project,
    limit: 1,
    skip: params.skip,
  });
  const count = callsStats.result?.count ?? 0;
  return useMemo(() => {
    return {
      loading: callsStats.loading,
      result: count > 0,
      error: callsStats.error,
    };
  }, [callsStats, count]);
};

const useCallsDeleteFunc = () => {
  const getTsClient = useGetTraceServerClientContext();

  const callsDelete = useCallback(
    (params: UseCallsDeleteParams): Promise<void> => {
      return getTsClient()
        .callsDelete({
          project_id: projectIdFromParts({
            entity: params.entity,
            project: params.project,
          }),
          call_ids: params.callIDs,
        })
        .then(() => {
          params.callIDs.forEach(callId => {
            callCache.del({
              entity: params.entity,
              project: params.project,
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
    (params: UseCallUpdateParams): Promise<void> => {
      return getTsClient()
        .callUpdate({
          project_id: projectIdFromParts({
            entity: params.entity,
            project: params.project,
          }),
          call_id: params.callID,
          display_name: params.newName,
        })
        .then(() => {
          callCache.del({
            entity: params.entity,
            project: params.project,
            callId: params.callID,
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
    (params: UseCallsExportParams) => {
      const req: traceServerTypes.TraceCallsQueryReq = {
        project_id: projectIdFromParts({
          entity: params.entity,
          project: params.project,
        }),
        filter: {
          op_names: params.filter.opVersionRefs,
          input_refs: params.filter.inputObjectVersionRefs,
          output_refs: params.filter.outputObjectVersionRefs,
          parent_ids: params.filter.parentIds,
          trace_ids: params.filter.traceId
            ? [params.filter.traceId]
            : undefined,
          call_ids: params.filter.callIds,
          trace_roots_only: params.filter.traceRootsOnly,
          wb_run_ids: params.filter.runIds,
          wb_user_ids: params.filter.userIds,
        },
        limit: params.limit,
        offset: params.offset,
        sort_by: params.sortBy,
        query: params.query,
        columns: params.columns ?? undefined,
        expand_columns: params.expandedRefCols ?? undefined,
        include_feedback: params.includeFeedback ?? false,
        include_costs: params.includeCosts ?? false,
        include_total_storage_size: (params.columns ?? []).includes(
          'total_storage_size_bytes'
        ),
      };
      return getTsClient().callsStreamDownload(req, params.contentType);
    },
    [getTsClient]
  );

  return downloadCallsExport;
};

const useFeedback = (
  params: UseFeedbackParams
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

  const deepKey = useDeepMemo(params.key);

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
        sort_by: params.sortBy ?? [{field: 'created_at', direction: 'desc'}],
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
  }, [deepKey, getTsClient, doReload, params.sortBy]);

  return {...result, refetch};
};

const useOpVersion = (
  params: UseOpVersionParams
): LoadableWithError<OpVersionSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const cachedOpVersion = params.key ? opVersionCache.get(params.key) : null;
  const [opVersionRes, setOpVersionRes] =
    useState<traceServerTypes.TraceObjReadRes | null>(null);
  const [error, setError] = useState<any>(null);
  const deepKey = useDeepMemo(params.key);
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
          metadata_only: params.metadataOnly ?? false,
        })
        .then(res => {
          loadingRef.current = false;
          setOpVersionRes(res);
          if (res.obj == null && !params.metadataOnly) {
            setError(new Error(JSON.stringify(res)));
            // be conservative and unset the cache when there's an error
            if (deepKey) {
              opVersionCache.del(deepKey);
            }
          }
        });
    }
  }, [deepKey, getTsClient, params.metadataOnly]);

  return useMemo(() => {
    if (params.key == null) {
      return {
        loading: false,
        result: null,
        error,
      };
    }
    if (cachedOpVersion != null) {
      return {
        loading: false,
        result: cachedOpVersion,
        error,
      };
    }
    if (opVersionRes == null || loadingRef.current) {
      return {
        loading: true,
        result: null,
        error,
      };
    }

    if (opVersionRes.obj == null) {
      return {
        loading: false,
        result: null,
        error,
      };
    }

    const returnedResult = convertTraceServerObjectVersionToOpSchema(
      opVersionRes.obj
    );

    if (
      params.key.entity !== returnedResult.entity ||
      params.key.project !== returnedResult.project ||
      params.key.opId !== returnedResult.opId ||
      params.key.versionHash !== returnedResult.versionHash
    ) {
      return {
        loading: true,
        result: null,
        error,
      };
    }

    const cacheableResult: OpVersionSchema = {
      ...params.key,
      ...returnedResult,
    };

    // Skip setting the cache if metadata only
    if (params.metadataOnly) {
      return {
        loading: false,
        result: cacheableResult,
        error,
      };
    }

    opVersionCache.set(params.key, cacheableResult);
    return {
      loading: false,
      result: cacheableResult,
      error,
    };
  }, [cachedOpVersion, params.key, opVersionRes, error, params.metadataOnly]);
};

const useOpVersions = (
  params: UseOpVersionsParams
): LoadableWithError<OpVersionSchema[]> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [opVersionRes, setOpVersionRes] = useState<
    LoadableWithError<OpVersionSchema[]>
  >({
    loading: false,
    error: null,
    result: null,
  });
  const deepFilter = useDeepMemo(params.filter);
  const deepOrderBy = useDeepMemo(params.orderBy);

  const doFetch = useCallback(() => {
    if (params.skip) {
      return;
    }
    setOpVersionRes({loading: true, error: null, result: null});
    loadingRef.current = true;

    const req: traceServerTypes.TraceObjQueryReq = {
      project_id: projectIdFromParts({
        entity: params.entity,
        project: params.project,
      }),
      filter: {
        object_ids: deepFilter.opIds,
        latest_only: deepFilter.latestOnly,
        is_op: true,
      },
      limit: params.limit,
      metadata_only: params.metadataOnly,
      sort_by: deepOrderBy,
    };
    const onSuccess = (res: traceServerTypes.TraceObjQueryRes) => {
      loadingRef.current = false;
      setOpVersionRes({
        loading: false,
        error: null,
        result: res.objs.map(convertTraceServerObjectVersionToOpSchema),
      });
    };
    const onError = (e: any) => {
      loadingRef.current = false;
      console.error(e);
      setOpVersionRes({loading: false, error: e, result: null});
    };
    getTsClient().objsQuery(req).then(onSuccess).catch(onError);
  }, [
    deepFilter,
    getTsClient,
    params.skip,
    params.entity,
    params.project,
    params.limit,
    params.metadataOnly,
    deepOrderBy,
  ]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    return getTsClient().registerOnObjectListener(doFetch);
  }, [getTsClient, doFetch]);

  return useMemo(() => {
    if (params.skip) {
      return {loading: false, error: null, result: null};
    }
    if (opVersionRes == null || loadingRef.current) {
      return {loading: true, error: null, result: null};
    }
    return opVersionRes;
  }, [opVersionRes, params.skip]);
};

// Helper function to convert trace server object version to op schema
const convertTraceServerObjectVersionToOpSchema = (
  obj: traceServerTypes.TraceObjSchema
): OpVersionSchema => {
  const {entity, project} = projectIdToParts(obj.project_id);
  return {
    entity,
    project,
    opId: obj.object_id,
    versionHash: obj.digest,
    createdAtMs: convertISOToDate(obj.created_at).getTime(),
    versionIndex: obj.version_index,
    userId: obj.wb_user_id,
  };
};

const useFileContent = (
  params: UseFileContentParams
): LoadableWithError<ArrayBuffer> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [fileContentRes, setFileContentRes] =
    useState<traceServerTypes.TraceFileContentReadRes | null>(null);
  const [error, setError] = useState<any>(null);

  useEffect(() => {
    if (params.skip) {
      return;
    }
    setFileContentRes(null);
    loadingRef.current = true;
    getTsClient()
      .fileContent({
        project_id: projectIdFromParts({
          entity: params.entity,
          project: params.project,
        }),
        digest: params.digest,
      })
      .then(res => {
        loadingRef.current = false;
        setFileContentRes(res);
      })
      .catch(err => {
        loadingRef.current = false;
        setError(err);
      });
  }, [getTsClient, params.entity, params.project, params.digest, params.skip]);

  return useMemo(() => {
    if (params.skip) {
      return {loading: false, result: null, error: null};
    }
    if (fileContentRes == null || loadingRef.current) {
      return {loading: true, result: null, error};
    }
    return {loading: false, result: fileContentRes.content, error};
  }, [fileContentRes, params.skip, error]);
};

const useObjectVersion = (
  params: UseObjectVersionParams
): LoadableWithError<ObjectVersionSchema | null> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const cachedObjectVersion = params.key
    ? objectVersionCache.get(params.key)
    : null;
  const [objectVersionRes, setObjectVersionRes] =
    useState<traceServerTypes.TraceObjReadRes | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const deepKey = useDeepMemo(params.key);
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
          metadata_only: params.metadataOnly ?? false,
        })
        .then(res => {
          loadingRef.current = false;
          if (res.obj == null) {
            if ('deleted_at' in res) {
              setError(new Error(JSON.stringify(res)));
            } else {
              setError(new Error('Object not found'));
            }
          } else {
            setObjectVersionRes(res);
          }
        })
        .catch(err => {
          setError(new Error(JSON.stringify(err)));
        });
    }
  }, [deepKey, getTsClient, params.metadataOnly]);

  return useMemo(() => {
    if (params.key == null) {
      return {
        loading: false,
        result: null,
        error,
      };
    }
    if (cachedObjectVersion != null) {
      return {
        loading: false,
        result: cachedObjectVersion,
        error,
      };
    }
    if (objectVersionRes == null || loadingRef.current) {
      return {
        loading: true,
        result: null,
        error,
      };
    }

    if (objectVersionRes.obj == null) {
      return {
        loading: false,
        result: null,
        error,
      };
    }

    const returnedResult: ObjectVersionSchema =
      convertTraceServerObjectVersionToSchema(objectVersionRes.obj);

    if (
      params.key.entity !== returnedResult.entity ||
      params.key.project !== returnedResult.project ||
      params.key.objectId !== returnedResult.objectId ||
      params.key.versionHash !== returnedResult.versionHash
    ) {
      return {
        loading: true,
        result: null,
        error,
      };
    }

    const cacheableResult: ObjectVersionSchema = {
      ...params.key,
      ...returnedResult,
    };

    // Skip setting the cache if metadata only
    if (params.metadataOnly) {
      return {
        loading: false,
        result: cacheableResult,
        error,
      };
    }

    objectVersionCache.set(params.key, cacheableResult);
    return {
      loading: false,
      result: cacheableResult,
      error,
    };
  }, [
    cachedObjectVersion,
    params.key,
    objectVersionRes,
    error,
    params.metadataOnly,
  ]);
};

export const convertTraceServerObjectVersionToSchema = <
  T extends traceServerTypes.TraceObjSchema
>(
  obj: T
): ObjectVersionSchema<T['val']> => {
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
    userId: obj.wb_user_id,
    sizeBytes: obj.size_bytes,
  };
};

const useRootObjectVersions = (
  params: UseRootObjectVersionsParams
): LoadableWithError<ObjectVersionSchema[]> => {
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [objectVersionRes, setObjectVersionRes] = useState<
    LoadableWithError<ObjectVersionSchema[]>
  >({
    loading: false,
    error: null,
    result: null,
  });
  const deepFilter = useDeepMemo(params.filter);

  const doFetch = useCallback(() => {
    if (params.skip) {
      return;
    }
    setObjectVersionRes({loading: true, error: null, result: null});
    loadingRef.current = true;

    const req: traceServerTypes.TraceObjQueryReq = {
      project_id: projectIdFromParts({
        entity: params.entity,
        project: params.project,
      }),
      filter: {
        base_object_classes: deepFilter?.baseObjectClasses,
        object_ids: deepFilter?.objectIds,
        latest_only: deepFilter?.latestOnly,
        is_op: false,
      },
      limit: params.limit,
      metadata_only: params.metadataOnly,
      ...(!!params.includeStorageSize ? {include_storage_size: true} : null),
    };
    const onSuccess = (res: traceServerTypes.TraceObjQueryRes) => {
      loadingRef.current = false;
      setObjectVersionRes({
        loading: false,
        error: null,
        result: res.objs?.map(convertTraceServerObjectVersionToSchema) ?? [],
      });
    };
    const onError = (e: any) => {
      loadingRef.current = false;
      console.error(e);
      setObjectVersionRes({loading: false, error: e, result: null});
    };
    getTsClient().objsQuery(req).then(onSuccess).catch(onError);
  }, [
    params.skip,
    params.entity,
    params.project,
    deepFilter,
    params.limit,
    params.metadataOnly,
    params.includeStorageSize,
    getTsClient,
  ]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  useEffect(() => {
    if (params.skip) {
      return;
    }
    if (params.noAutoRefresh) {
      return;
    }
    return getTsClient().registerOnObjectListener(doFetch);
  }, [getTsClient, doFetch, params.skip, params.noAutoRefresh]);

  return useMemo(() => {
    if (params.skip) {
      return {loading: false, error: null, result: null};
    }
    if (objectVersionRes == null || loadingRef.current) {
      return {loading: true, error: null, result: null};
    }
    return objectVersionRes;
  }, [objectVersionRes, params.skip]);
};

const useObjectDeleteFunc = () => {
  const getTsClient = useGetTraceServerClientContext();

  const makeObjectRef = (key: ObjectVersionKey) => {
    const ref: WeaveObjectRef = {
      scheme: 'weave',
      entityName: key.entity,
      projectName: key.project,
      weaveKind: 'object',
      artifactName: key.objectId,
      artifactVersion: key.versionHash,
    };
    return refUri(ref);
  };

  const makeOpRef = (key: OpVersionKey) => {
    const ref: WeaveObjectRef = {
      scheme: 'weave',
      entityName: key.entity,
      projectName: key.project,
      weaveKind: 'op',
      artifactName: key.opId,
      artifactVersion: key.versionHash,
    };
    return refUri(ref);
  };

  const updateObjectCaches = useCallback((key: ObjectVersionKey) => {
    objectVersionCache.del(key);
    const ref = makeObjectRef(key);
    refDataCache.del(ref);
  }, []);

  const updateOpCaches = useCallback((key: OpVersionKey) => {
    opVersionCache.del(key);
    const ref = makeOpRef(key);
    refDataCache.del(ref);
  }, []);

  const objectVersionsDelete = useCallback(
    (params: ObjectDeleteParams) => {
      params.digests?.forEach(digest => {
        updateObjectCaches({
          scheme: 'weave',
          weaveKind: 'object',
          entity: params.entity,
          project: params.project,
          objectId: params.objectId,
          versionHash: digest,
          path: '',
        });
      });
      return getTsClient().objDelete({
        project_id: projectIdFromParts({
          entity: params.entity,
          project: params.project,
        }),
        object_id: params.objectId,
        digests: params.digests,
      });
    },
    [getTsClient, updateObjectCaches]
  );

  const objectDeleteAllVersions = useCallback(
    (params: ObjectDeleteAllVersionsParams) => {
      updateObjectCaches(params.key);
      return getTsClient().objDelete({
        project_id: projectIdFromParts({
          entity: params.key.entity,
          project: params.key.project,
        }),
        object_id: params.key.objectId,
        digests: [],
      });
    },
    [getTsClient, updateObjectCaches]
  );

  const opVersionsDelete = useCallback(
    (params: OpVersionDeleteParams) => {
      params.digests?.forEach(digest => {
        updateOpCaches({
          entity: params.entity,
          project: params.project,
          opId: params.opId,
          versionHash: digest,
        });
      });
      return getTsClient().objDelete({
        project_id: projectIdFromParts({
          entity: params.entity,
          project: params.project,
        }),
        object_id: params.opId,
        digests: params.digests,
      });
    },
    [getTsClient, updateOpCaches]
  );

  const opDeleteAllVersions = useCallback(
    (params: OpVersionDeleteAllVersionsParams) => {
      updateOpCaches(params.key);
      return getTsClient().objDelete({
        project_id: projectIdFromParts({
          entity: params.key.entity,
          project: params.key.project,
        }),
        object_id: params.key.opId,
        digests: [],
      });
    },
    [getTsClient, updateOpCaches]
  );

  return {
    objectVersionsDelete,
    objectDeleteAllVersions,
    opVersionsDelete,
    opDeleteAllVersions,
  };
};

const useRefsReadBatch = (params: UseRefsReadBatchParams) => {
  const getTsClient = useGetTraceServerClientContext();
  // Here we keep track of the result and the uris we fetched for. This is
  // because repeated calls to this hook with different uris will return
  // could result in stale results if we just returned the result from the
  // hook.
  const [refsRes, setRefsRes] = useState<{
    res: traceServerTypes.TraceRefsReadBatchRes;
    forUris: string[];
  } | null>(null);
  const loadingRef = useRef(false);

  const deepRefUris = useDeepMemo(params.refUris);

  useEffect(() => {
    if (params.skip || deepRefUris.length === 0) {
      return;
    }
    setRefsRes(null);
    loadingRef.current = true;
    getTsClient()
      .readBatch({
        refs: deepRefUris,
      })
      .then((res: traceServerTypes.TraceRefsReadBatchRes) => {
        loadingRef.current = false;
        setRefsRes({res, forUris: deepRefUris});
      })
      .catch((err: Error) => {
        loadingRef.current = false;
        console.error('Error fetching refs:', err);
        setRefsRes(null);
      });
  }, [getTsClient, deepRefUris, params.skip]);

  return useMemo(() => {
    if (params.skip || params.refUris.length === 0) {
      return {loading: false, result: null};
    }
    if (
      refsRes == null ||
      loadingRef.current ||
      refsRes.forUris !== deepRefUris
    ) {
      return {loading: true, result: null};
    }
    return {loading: false, result: refsRes.res.vals};
  }, [params.skip, params.refUris.length, refsRes, deepRefUris]);
};

const useTableQuery = makeTraceServerEndpointHook<
  'tableQuery',
  UseTableQueryParams,
  traceServerTypes.TraceTableQueryRes['rows']
>(
  'tableQuery',
  params => ({
    params: {
      project_id: params.projectId,
      digest: params.digest,
      filter: params.filter,
      limit: params.limit,
      offset: params.offset,
      sort_by: params.sortBy,
    },
    skip: params.skip,
  }),
  res => res.rows
);

const useChildCallsForCompare = (
  params: UseChildCallsForCompareParams
): Loadable<CallSchema[]> => {
  // This should be moved to the trace server soon. Doing in memory join for
  // feature completeness now.
  const skipParent =
    params.parentCallIds == null ||
    params.parentCallIds.length === 0 ||
    params.selectedObjectVersionRef == null;

  const parentCalls = useCalls({
    entity: params.entity,
    project: params.project,
    filter: {
      callIds: params.parentCallIds,
      inputObjectVersionRefs: params.selectedObjectVersionRef
        ? [params.selectedObjectVersionRef]
        : [],
    },
    skip: skipParent,
  });

  const subParentCallIds = useMemo(() => {
    return (parentCalls.result ?? []).map(call => call.callId);
  }, [parentCalls.result]);

  const skipChild =
    subParentCallIds.length === 0 || params.selectedOpVersionRef == null;

  const childCalls = useCalls({
    entity: params.entity,
    project: params.project,
    filter: {
      parentIds: subParentCallIds,
      opVersionRefs: params.selectedOpVersionRef
        ? [params.selectedOpVersionRef]
        : [],
    },
    skip: skipChild,
  });

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

const useRefsData = (params: UseRefsDataParams): Loadable<any[]> => {
  const refUrisDeep = useDeepMemo(params.refUris);

  const [nonTableRefUris, tableRefUris] = useMemo(() => {
    const sUris: string[] = [];
    const tUris: string[] = [];
    refUrisDeep
      .map(uri => {
        return {uri, ref: refUriToObjectVersionKey(uri)};
      })
      .forEach(({uri, ref}, ndx) => {
        if (ref) {
          if (ref.scheme === 'weave' && ref.weaveKind === 'table') {
            tUris.push(uri);
          } else {
            sUris.push(uri);
          }
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

  const simpleValsResult = useRefsReadBatch({
    refUris: neededSimpleUris,
    skip: neededSimpleUris.length === 0,
  });
  let tableUriProjectId = '';
  let tableUriDigest = '';
  if (tableRefUris.length > 1) {
    throw new Error('Multiple table refs not supported');
  } else if (tableRefUris.length === 1) {
    const tableRef = refUriToObjectVersionKey(tableRefUris[0])!;
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
      params.tableQuery?.limit?.toString()
    );
  }, [params.tableQuery?.limit, tableQueryFilter, tableRefUris]);

  const cachedTableResult = refDataCache.get(tableRefKey);

  const tableQueryParams = useMemo(
    () => ({
      projectId: tableUriProjectId,
      digest: tableUriDigest,
      filter: tableQueryFilter,
      limit: params.tableQuery?.limit,
      skip: tableRefUris.length === 0 || cachedTableResult != null,
    }),
    [
      tableUriProjectId,
      tableUriDigest,
      tableQueryFilter,
      params.tableQuery?.limit,
      tableRefUris,
      cachedTableResult,
    ]
  );
  const tableValsResult = useTableQuery(tableQueryParams);

  return useMemo(() => {
    if (params.refUris.length === 0) {
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
    const valsResult = params.refUris.map(uri => valueMap.get(uri));

    return {
      loading: false,
      result: valsResult,
      error: null,
    };
  }, [
    params.refUris,
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

const useTableRowsQuery = (
  params: UseTableRowsQueryParams
): Loadable<traceServerTypes.TraceTableQueryRes> => {
  const getTsClient = useGetTraceServerClientContext();
  const [queryRes, setQueryRes] =
    useState<traceServerTypes.TraceTableQueryRes | null>(null);
  const loadingRef = useRef(false);

  const projectId = projectIdFromParts({
    entity: params.entity,
    project: params.project,
  });

  const doFetch = useCallback(() => {
    if (params.skip) {
      return;
    }
    setQueryRes(null);
    loadingRef.current = true;

    const req: traceServerTypes.TraceTableQueryReq = {
      project_id: projectId,
      digest: params.digest,
      filter: params.filter,
      limit: params.limit,
      offset: params.offset,
      sort_by: params.sortBy,
    };

    getTsClient()
      .tableQuery(req)
      .then(res => {
        loadingRef.current = false;
        setQueryRes(res);
      })
      .catch(err => {
        loadingRef.current = false;
        console.error('Error fetching table rows:', err);
        setQueryRes(null);
      });
  }, [
    getTsClient,
    projectId,
    params.digest,
    params.filter,
    params.limit,
    params.offset,
    params.sortBy,
    params.skip,
  ]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  return useMemo(() => {
    if (params.skip) {
      return {loading: false, result: null};
    }
    if (queryRes == null || loadingRef.current) {
      return {loading: true, result: null};
    }
    return {loading: false, result: queryRes};
  }, [queryRes, params.skip]);
};

const useTableQueryStats = (
  params: UseTableQueryStatsParams
): Loadable<traceServerTypes.TraceTableQueryStatsBatchRes> => {
  const getTsClient = useGetTraceServerClientContext();
  const [queryRes, setQueryRes] =
    useState<traceServerTypes.TraceTableQueryStatsBatchRes | null>(null);
  const loadingRef = useRef(false);

  const projectId = projectIdFromParts({
    entity: params.entity,
    project: params.project,
  });

  const doFetch = useCallback(() => {
    if (params.skip) {
      return;
    }
    setQueryRes(null);
    loadingRef.current = true;

    const req: traceServerTypes.TraceTableQueryStatsBatchReq = {
      project_id: projectId,
      digests: params.digests,
      include_storage_size: params.includeStorageSize,
    };

    getTsClient()
      .tableQueryStatsBatch(req)
      .then(res => {
        loadingRef.current = false;
        setQueryRes(res);
      })
      .catch(err => {
        loadingRef.current = false;
        console.error('Error fetching table stats:', err);
        setQueryRes(null);
      });
  }, [
    getTsClient,
    projectId,
    params.digests,
    params.includeStorageSize,
    params.skip,
  ]);

  useEffect(() => {
    doFetch();
  }, [doFetch]);

  return useMemo(() => {
    if (params.skip) {
      return {loading: false, result: null};
    }
    if (queryRes == null || loadingRef.current) {
      return {loading: true, result: null};
    }
    return {loading: false, result: queryRes};
  }, [queryRes, params.skip]);
};

const useTableUpdate = () => {
  const getTsClient = useGetTraceServerClientContext();

  return useCallback(
    (params: UseTableUpdateParams) => {
      return getTsClient().tableUpdate({
        project_id: params.projectId,
        base_digest: params.baseDigest,
        updates: params.updates,
      });
    },
    [getTsClient]
  );
};

const useApplyMutationsToRef = (): ((
  params: UseApplyMutationsToRefParams
) => Promise<string>) => {
  throw new Error('Not implemented');
};

const useGetRefsType = () => {
  const readBatch = useMakeTraceServerEndpoint(
    'readBatch',
    (params: UseGetRefsTypeParams) => ({
      refs: params.refUris,
    }),
    (res): any[] => res.vals
  );
  return async (params: UseGetRefsTypeParams): Promise<Types.Type[]> => {
    if (params.refUris.length === 0) {
      return [];
    }
    const needed: string[] = [];
    const refToData: Record<string, any> = {};
    params.refUris.forEach(uri => {
      const res = refDataCache.get(uri);
      if (res == null) {
        needed.push(uri);
      } else {
        refToData[uri] = res;
      }
    });
    if (needed.length !== 0) {
      const readBatchResults = await readBatch(params);
      readBatchResults.forEach((res, i) => {
        refToData[needed[i]] = res;
        refDataCache.set(needed[i], res);
      });
    }
    return params.refUris.map(uri => weaveTypeOf(refToData[uri]));
  };
};

const useCodeForOpRef = (opVersionRef: string): Loadable<string> => {
  const query = useRefsData({refUris: [opVersionRef]});
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
  const arrayBuffer = useFileContent({
    entity: fileSpec?.entity ?? '',
    project: fileSpec?.project ?? '',
    digest: fileSpec?.digest ?? '',
    skip: fileSpec == null,
  });
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

const useRefsType = (params: UseGetRefsTypeParams): Loadable<Types.Type[]> => {
  const dataResult = useRefsData({refUris: params.refUris});
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

/**
 * Getting the status code for a trace call has a few complexities.
 */
export const traceCallStatusCode = (
  traceCall: traceServerTypes.TraceCallSchema,
  hasDescendantErrors?: boolean
): traceServerTypes.ComputedCallStatusType => {
  const serverSideStatus = traceCall.summary?.weave?.status;
  if (serverSideStatus) {
    if (
      serverSideStatus === traceServerTypes.ComputedCallStatuses.success &&
      hasDescendantErrors
    ) {
      return traceServerTypes.ComputedCallStatuses.descendant_error;
    }
    return serverSideStatus;
  }
  if (traceCall.exception) {
    return traceServerTypes.ComputedCallStatuses.error;
  } else if (traceCall.ended_at) {
    const errors = traceCall.summary?.status_counts?.error ?? 0;
    if (errors > 0 || hasDescendantErrors) {
      return traceServerTypes.ComputedCallStatuses.descendant_error;
    }
    return traceServerTypes.ComputedCallStatuses.success;
  }
  return traceServerTypes.ComputedCallStatuses.running;
};

export const traceCallLatencyS = (
  traceCall: traceServerTypes.TraceCallSchema
) => {
  return traceCallLatencyMs(traceCall) / 1000;
};

export const traceCallLatencyMs = (
  traceCall: traceServerTypes.TraceCallSchema
) => {
  const startDate = convertISOToDate(traceCall.started_at);
  const endDate = traceCall.ended_at
    ? convertISOToDate(traceCall.ended_at)
    : null;
  if (startDate == null || endDate == null) {
    return 0;
  }
  return endDate.getTime() - startDate.getTime();
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

export const parseSpanName = (opName: string) => {
  if (
    opName.startsWith(WANDB_ARTIFACT_REF_PREFIX) ||
    opName.startsWith(WEAVE_REF_PREFIX)
  ) {
    return opVersionRefOpName(opName);
  }
  if (opName.startsWith(WEAVE_PRIVATE_PREFIX)) {
    return privateRefToSimpleName(opName);
  }
  return opName;
};

export const traceCallToUICallSchema = (
  traceCall: traceServerTypes.TraceCallSchema
): CallSchema => {
  const {entity, project} = projectIdToParts(traceCall.project_id);

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
    totalStorageSizeBytes: traceCall.total_storage_size_bytes ?? null,
  };
};

export const useObjCreate = () => {
  const getTsClient = useGetTraceServerClientContext();

  return useCallback(
    (params: UseObjCreateParams) => {
      return getTsClient()
        .objCreate({
          obj: {
            project_id: params.projectId,
            object_id: params.objectId,
            val: params.val,
            builtin_object_class: params.baseObjectClass,
          },
        })
        .then(res => {
          return res.digest;
        });
    },
    [getTsClient]
  );
};

export const useTableCreate = (): ((
  table: traceServerTypes.TableCreateReq
) => Promise<traceServerTypes.TableCreateRes>) => {
  const getTsClient = useGetTraceServerClientContext();

  return useCallback(
    (table: traceServerTypes.TableCreateReq) => {
      return getTsClient().tableCreate(table);
    },
    [getTsClient]
  );
};

export const useProjectStats = (projectId: string) => {
  const getTsClient = useGetTraceServerClientContext();

  return useAsync(async () => {
    return getTsClient().projectStats({project_id: projectId});
  }, [getTsClient, projectId]);
};

/// Utility Functions ///

export const convertISOToDate = (iso: string): Date => {
  return new Date(iso);
};

export const tsWFDataModelHooks: WFDataModelHooksInterface = {
  useCall,
  useCalls,
  useCallsStats,
  useProjectHasCalls,
  useCallsDeleteFunc,
  useCallUpdateFunc,
  useCallsExport,
  useObjCreate,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useObjectDeleteFunc,
  useRootObjectVersions,
  useRefsData,
  useApplyMutationsToRef,
  useFeedback,
  useFileContent,
  useTableRowsQuery,
  useTableQueryStats,
  useTableUpdate,
  useTableCreate,
  derived: {
    useChildCallsForCompare,
    useGetRefsType,
    useRefsType,
    useCodeForOpRef,
  },
};
