/**
 * This file defines `tsWFDataModelHooks` which conforms to the the
 * `WFDataModelHooksInterface`, providing access to the Weaveflow data model
 * backed by the "Trace Server" engine.
 */

import {useEffect, useMemo, useRef, useState} from 'react';

import {useDeepMemo} from '../../../../../../hookUtils';
import {getCallFromCache, setCallInCache} from './cache';
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
  WFDataModelHooksInterface,
} from './wfDataModelHooksInterface';

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
  const cachedCall = key ? getCallFromCache(key) : null;
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
  const getTsClient = useGetTraceServerClientContext();
  const loadingRef = useRef(false);
  const [callRes, setCallRes] =
    useState<traceServerClient.TraceCallsQueryRes | null>(null);
  const deepFilter = useDeepMemo(filter);
  useEffect(() => {
    if (opts?.skip) {
      return;
    }
    setCallRes(null);
    loadingRef.current = true;
    getTsClient()
      .callsQuery({
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
        limit,
      })
      .then(res => {
        loadingRef.current = false;
        setCallRes(res);
      })
      .catch(e => {
        // Temp fix before more robust error handling
        loadingRef.current = false;
        console.error(e);
        setCallRes({calls: []});
      });
  }, [entity, project, deepFilter, limit, opts?.skip, getTsClient]);

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
      console.log(result)
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
  derived: {
    useChildCallsForCompare,
  },
};
