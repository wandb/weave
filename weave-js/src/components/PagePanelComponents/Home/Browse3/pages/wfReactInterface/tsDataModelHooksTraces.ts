import {useEffect, useState} from 'react';

import {TraceServerClient} from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {TraceCallSchema} from './traceServerClientTypes';
import {LoadableWithError} from './wfDataModelHooksInterface';

export const useBareTraceCalls = (
  entity: string,
  project: string,
  traceId: string
): LoadableWithError<TraceCallSchema[]> => {
  const getClient = useGetTraceServerClientContext();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [traceCalls, setTraceCalls] = useState<TraceCallSchema[]>([]);

  useEffect(() => {
    let mounted = true;
    const fetchCalls = async () => {
      try {
        const client = getClient();
        const res = await fetchBareTraceCalls(client, entity, project, traceId);

        if (mounted) {
          setTraceCalls(res);
          setLoading(false);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          setError(err as Error);
          setLoading(false);
        }
      }
    };

    // Initial fetch
    fetchCalls();

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
    sort_by: [{field: 'started_at', direction: 'asc'}],
    columns: [
      'project_id',
      'id',
      'op_name',
      'display_name',
      'trace_id',
      'parent_id',
      'started_at',
      'ended_at',
      'exception',
      'wb_run_id',
      'wb_user_id',
      'summary',
    ],
    include_costs: true,
    include_feedback: false,
  });
  return traceCallsProm.then(res => res.calls);
};
