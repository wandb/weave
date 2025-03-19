import {useEffect, useState} from 'react';

import {TraceServerClient} from './traceServerClient';
import {useGetTraceServerClientContext} from './traceServerClientContext';
import {TraceCallSchema} from './traceServerClientTypes';
import {LoadableWithError} from './wfDataModelHooksInterface';

/**
 * Fetches the "bare" trace calls for a given trace ID. Where "bare" means
 * simply means calls without any additional json fields or feedback. The
 * first load will optimize for speed and not have costs, where the second
 * load will have costs.
 */
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
        const resProm = fetchBareTraceCalls(client, entity, project, traceId);
        // The backend has a bug where calls that are unfinished do not return at all
        // when requesting costs. Therefore, we have to do a second fetch to get costs
        // and zip the results together - BAD!. FIXME.
        resProm.then(res => {
          if (mounted) {
            setTraceCalls(res);
            setLoading(false);
            setError(null);
            const resWithCostsProm = fetchBareTraceCallsWithCosts(
              client,
              entity,
              project,
              traceId
            );
            resWithCostsProm.then(resWithCosts => {
              if (mounted) {
                setTraceCalls(currCalls => {
                  // First, make a map of the calls with cost by id:
                  const callsWithCosts = new Map<string, TraceCallSchema>();
                  resWithCosts.forEach(call => {
                    callsWithCosts.set(call.id, call);
                  });
                  // Then, update the calls in the current list with the costs:
                  return currCalls.map(call => {
                    return callsWithCosts.get(call.id) ?? call;
                  });
                });
              }
            });
          }
        });
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

/**
 * Fetches the "bare" trace calls for a given trace ID. Where "bare" means
 * simply means calls without any additional json fields, costs, or feedback
 */
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
    ],
    include_costs: false,
    include_feedback: false,
  });
  return traceCallsProm.then(res => res.calls);
};

/**
 * Fetches the "bare" trace calls for a given trace ID. Where "bare" means
 * simply means calls without any additional json fields or feedback, but
 * does include costs
 */
const fetchBareTraceCallsWithCosts = (
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
