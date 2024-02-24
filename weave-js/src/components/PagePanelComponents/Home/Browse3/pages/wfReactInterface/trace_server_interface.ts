import {useEffect, useMemo, useRef, useState} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {getCallFromCache, setCallInCache} from './cache';
import {WANDB_ARTIFACT_REF_PREFIX} from './constants';
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
} from './interface';
import * as trace_server_client from './trace_server_client';
import {opVersionRefOpCategory, refUriToOpVersionKey} from './utilities';

const useCall = (key: CallKey | null): Loadable<CallSchema | null> => {
  const loadingRef = useRef(false);
  const cachedCall = key ? getCallFromCache(key) : null;
  const [callRes, setCallRes] =
    useState<trace_server_client.TraceCallReadRes | null>(null);
  const deepKey = useDeepMemo(key);
  useEffect(() => {
    if (deepKey) {
      setCallRes(null);
      loadingRef.current = true;
      trace_server_client
        .callRead({
          entity: deepKey.entity,
          project: deepKey.project,
          id: deepKey.callId,
        })
        .then(res => {
          loadingRef.current = false;
          setCallRes(res);
        });
    }
  }, [deepKey]);

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
        setCallInCache(key, result);
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
  const loadingRef = useRef(false);
  const [callRes, setCallRes] =
    useState<trace_server_client.TraceCallsQueryRes | null>(null);
  const deepFilter = useDeepMemo(filter);
  useEffect(() => {
    if (opts?.skip) {
      return;
    }
    setCallRes(null);
    loadingRef.current = true;
    trace_server_client
      .callsQuery({
        entity,
        project,
        filter: {
          op_version_refs: deepFilter.opVersionRefs,
          input_object_version_refs: deepFilter.inputObjectVersionRefs,
          output_object_version_refs: deepFilter.outputObjectVersionRefs,
          parent_ids: deepFilter.parentIds,
          trace_ids: deepFilter.traceId ? [deepFilter.traceId] : undefined,
          call_ids: deepFilter.callIds,
          trace_roots_only: deepFilter.traceRootsOnly,
        },
        limit,
      })
      .then(res => {
        setCallRes(res);
        loadingRef.current = false;
      })
      .catch(e => {
        // Temp fix before more robust error handling
        console.error(e);
        setCallRes({calls: []});
        loadingRef.current = false;
      });
  }, [entity, project, deepFilter, limit, opts?.skip]);

  return useMemo(() => {
    if (opts?.skip) {
      return {
        loading: false,
        result: [],
      };
    }
    const allResults = (callRes?.calls ?? []).map(traceCallToUICallSchema);
    const result = allResults.filter((row: any) => {
      return (
        deepFilter.opCategory == null ||
        (row.opVersionRef &&
          deepFilter.opCategory.includes(
            opVersionRefOpCategory(row.opVersionRef) as OpCategory
          ))
      );
    });

    if (callRes == null || loadingRef.current) {
      return {
        loading: true,
        result: [],
      };
    } else {
      allResults.forEach(call => {
        setCallInCache(
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
  }, [callRes, deepFilter.opCategory, entity, project, opts?.skip]);
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
    {skip: selectedObjectVersionRef == null}
  );

  const subParentCallIds = useMemo(() => {
    return (parentCalls.result ?? []).map(call => call.callId);
  }, [parentCalls.result]);

  const childCalls = useCalls(
    entity,
    project,
    {
      parentIds: subParentCallIds,
      opVersionRefs: selectedOpVersionRef ? [selectedOpVersionRef] : [],
    },
    undefined,
    {skip: selectedOpVersionRef == null}
  );

  const result = useMemo(() => {
    const loading = parentCalls.loading || childCalls.loading;
    if (loading) {
      return {loading, result: []};
    }

    const parentCallsById: {[key: string]: CallSchema} = {};
    for (const call of parentCalls.result ?? []) {
      parentCallsById[call.callId] = call;
    }

    return {loading: false, result: childCalls.result ?? []};
  }, [
    childCalls.loading,
    childCalls.result,
    parentCalls.loading,
    parentCalls.result,
  ]);

  return result;
};

/// Converters ///

const traceCallToLegacySpan = (
  traceCall: trace_server_client.TraceCallSchema
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

const traceCallToUICallSchema = (
  traceCall: trace_server_client.TraceCallSchema
): CallSchema => {
  return {
    entity: traceCall.entity,
    project: traceCall.project,
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
  };
};

/// Utility Functions ///

const convertISOToDate = (iso: string) => {
  return new Date(iso);
};

// Export //

export const tsDataModelInterface = {
  useCall,
  useCalls,
  useOpVersion,
  useOpVersions,
  useObjectVersion,
  useRootObjectVersions,
  derived: {
    useChildCallsForCompare,
  },
};
