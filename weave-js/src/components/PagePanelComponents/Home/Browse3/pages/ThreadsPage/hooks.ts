import {useEffect, useMemo, useState} from 'react';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {LoadableWithError} from '../wfReactInterface/wfDataModelHooksInterface';

export const useThreadList = (
  entity: string,
  project: string
): LoadableWithError<string[]> => {
  // TODO: Implement this
  return useMemo(() => {
    return {
      loading: false,
      error: null,
      result: ['thread-id-1', 'thread-id-2'],
    };
  }, []);
};

export const useTracesForThread = (
  entity: string,
  project: string,
  threadId?: string
): LoadableWithError<string[]> => {
  const getClient = useGetTraceServerClientContext();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [traces, setTraces] = useState<string[]>([]);

  useEffect(() => {
    if (!threadId) {
      setTraces([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    let mounted = true;
    const client = getClient();
    fetchBareThreadTraces(client, entity, project, threadId)
      .then(res => {
        if (mounted) {
          setTraces(res.map(c => c.trace_id));
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          setError(err);
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [entity, getClient, project, threadId]);

  return {
    loading,
    error,
    result: traces,
  };
};

export const useBareTraceCalls = (
  entity: string,
  project: string,
  traceId?: string
): LoadableWithError<TraceCallSchema[]> => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [traceCalls, setTraceCalls] = useState<TraceCallSchema[]>([]);
  const getClient = useGetTraceServerClientContext();

  useEffect(() => {
    if (!traceId) {
      setTraceCalls([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    let mounted = true;
    const client = getClient();

    fetchBareTraceCalls(client, entity, project, traceId)
      .then(res => {
        if (mounted) {
          setTraceCalls(res);
          setLoading(false);
        }
      })
      .catch(err => {
        if (mounted) {
          setError(err);
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, [entity, getClient, project, traceId]);

  return {
    loading,
    error,
    result: traceCalls,
  };
};

const fetchBareThreadTraces = (
  client: TraceServerClient,
  entity: string,
  project: string,
  threadId: string
): Promise<TraceCallSchema[]> => {
  const traceCallsProm = client.callsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      trace_roots_only: true,
      // TODO: This is a placeholder for dev
      op_names: ['weave:///company-of-agents/mini-lms/op/Agent.go:*'],
    },
    limit: 10,
    sort_by: [{field: 'started_at', direction: 'desc'}],
    columns: [
      'project_id',
      'id',
      'op_name',
      'display_name',
      'trace_id',
      'parent_id',
      'started_at',
      'attributes',
      'inputs',
      'ended_at',
      'exception',
      'summary',
      'wb_run_id',
      'wb_user_id',
    ],
    include_costs: false,
    include_feedback: false,
  });
  return traceCallsProm.then(res => res.calls);
};

const fetchBareTraceCalls = (
  client: TraceServerClient,
  entity: string,
  project: string,
  traceId: string
): Promise<TraceCallSchema[]> => {
  const traceCallsProm = client.callsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      trace_ids: [traceId],
    },
    sort_by: [{field: 'started_at', direction: 'desc'}],
    columns: [
      'project_id',
      'id',
      'op_name',
      'display_name',
      'trace_id',
      'parent_id',
      'started_at',
      'attributes',
      'inputs',
      'ended_at',
      'exception',
      'summary',
      'wb_run_id',
      'wb_user_id',
    ],
    include_costs: false,
    include_feedback: false,
  });
  return traceCallsProm.then(res => res.calls);
};
