import {useEffect, useMemo, useState} from 'react';
import React from 'react';

import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {LoadableWithError} from '../wfReactInterface/wfDataModelHooksInterface';

/**
 * Hook to fetch and manage the list of available threads.
 * Currently returns a static list for development.
 * 
 * @param entity - The entity (organization/user) context
 * @param project - The project context
 * @returns LoadableWithError containing the list of thread IDs
 */
export const useThreadList = (
  entity: string,
  project: string
): LoadableWithError<string[]> => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [threads, setThreads] = useState<string[]>([]);

  useEffect(() => {
    // Simulate API call for now
    setLoading(true);
    setTimeout(() => {
      setThreads(['thread-id-1', 'thread-id-2']);
      setLoading(false);
    }, 500);
  }, [entity, project]);

  return {
    loading,
    error,
    result: threads,
  };
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
    sort_by: [{field: 'started_at', direction: 'asc'}],
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

/**
 * Hook to handle scrolling an element into view when a condition is met
 * @param elementRef - Reference to the element to scroll
 * @param shouldScroll - Condition that triggers the scroll
 * @param options - ScrollIntoView options
 */
export const useScrollIntoView = (
  elementRef: React.RefObject<HTMLElement>,
  shouldScroll: boolean,
  options: ScrollIntoViewOptions = {
    behavior: 'smooth',
    block: 'center',
  }
) => {
  React.useEffect(() => {
    let mounted = true;
    const doScroll = () => {
      if (mounted && shouldScroll && elementRef.current) {
        elementRef.current.scrollIntoView(options);
      }
    };

    const timeout = setTimeout(doScroll, 15);
    return () => {
      mounted = false;
      clearTimeout(timeout);
    };
  }, [elementRef, shouldScroll, options]);
};
