import {useCallback, useEffect, useState} from 'react';
import React from 'react';

import {useWFHooks} from '../wfReactInterface/context';
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
  const [error] = useState<Error | null>(null);
  const [threads, setThreads] = useState<string[]>([]);

  useEffect(() => {
    // Simulate API call for now
    setLoading(true);
    setTimeout(() => {
      setThreads(['_roots_']);
      setLoading(false);
    }, 500);
  }, [entity, project]);

  return {
    loading,
    error,
    result: threads,
  };
};

export const useTraceRootsForThread = (
  entity: string,
  project: string,
  threadId?: string,
  pollIntervalMs: number = 0
): LoadableWithError<TraceCallSchema[]> => {
  const getClient = useGetTraceServerClientContext();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [traces, setTraces] = useState<TraceCallSchema[]>([]);

  useEffect(() => {
    if (!threadId) {
      setTraces([]);
      setLoading(false);
      return;
    }

    let mounted = true;
    let pollTimeout: NodeJS.Timeout | null = null;

    const fetchTraces = async () => {
      try {
        const client = getClient();
        const res = await fetchBareThreadTraces(
          client,
          entity,
          project,
          threadId
        );
        if (mounted) {
          setTraces(res);
          setLoading(false);
          setError(null);

          // Schedule next poll if interval is set
          if (pollIntervalMs > 0 && mounted) {
            pollTimeout = setTimeout(fetchTraces, pollIntervalMs);
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err as Error);
          setLoading(false);

          // On error, retry after the same interval
          if (pollIntervalMs > 0 && mounted) {
            pollTimeout = setTimeout(fetchTraces, pollIntervalMs);
          }
        }
      }
    };

    // Initial fetch
    fetchTraces();

    return () => {
      mounted = false;
      if (pollTimeout) {
        clearTimeout(pollTimeout);
      }
    };
  }, [entity, getClient, project, threadId, pollIntervalMs]);

  return {
    loading,
    error,
    result: traces,
  };
};

export const useBareTraceCalls = (
  entity: string,
  project: string,
  traceId?: string,
  pollIntervalMs: number = 0
): LoadableWithError<TraceCallSchema[]> => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [traceCalls, setTraceCalls] = useState<TraceCallSchema[]>([]);
  // const [shouldPoll, setShouldPoll] = useState(true);
  const getClient = useGetTraceServerClientContext();

  useEffect(() => {
    if (!traceId) {
      setTraceCalls([]);
      setLoading(false);
      return;
    }

    let mounted = true;
    let pollTimeout: NodeJS.Timeout | undefined;

    const fetchCalls = async () => {
      try {
        const client = getClient();
        const res = await fetchBareTraceCalls(client, entity, project, traceId);

        if (mounted) {
          setTraceCalls(res);
          setLoading(false);
          setError(null);

          // Check if any call in the trace is still running
          const hasRunningCalls = res.some(call => !call.ended_at);
          // setShouldPoll(hasRunningCalls);

          // Schedule next poll if we should continue polling
          if (hasRunningCalls && pollIntervalMs > 0) {
            pollTimeout = setTimeout(fetchCalls, pollIntervalMs);
          }
        }
      } catch (err) {
        if (mounted) {
          setError(err as Error);
          setLoading(false);
          // Continue polling on error
          // setShouldPoll(true);
          if (pollIntervalMs > 0) {
            pollTimeout = setTimeout(fetchCalls, pollIntervalMs);
          }
        }
      }
    };

    // Initial fetch
    fetchCalls();

    return () => {
      mounted = false;
      if (pollTimeout) {
        clearTimeout(pollTimeout);
      }
    };
  }, [entity, getClient, project, traceId, pollIntervalMs]);

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
  let query: any = {
    $expr: {$eq: [{$getField: 'attributes.thread_id'}, {$literal: threadId}]},
  };
  if (threadId === '_roots_') {
    query = undefined;
  }
  const traceCallsProm = client.callsQuery({
    project_id: `${entity}/${project}`,
    filter: {
      trace_roots_only: true,
    },
    query,
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
      'output',
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

interface CallResult {
  traceCall: TraceCallSchema;
}

/**
 * Hook to poll a call until it completes
 */
export const usePollingCall = (
  entity: string,
  project: string,
  callId: string,
  pollIntervalMs: number = 1000
) => {
  const {useCall} = useWFHooks();
  const getClient = useGetTraceServerClientContext();
  const [polledCall, setPolledCall] = useState<CallResult | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [shouldPoll, setShouldPoll] = useState(true);

  // Initial call data
  const initialCallResult = useCall({
    entity,
    project,
    callId,
  });

  // Function to fetch call data directly
  const fetchCall = useCallback(async () => {
    try {
      const client = getClient();
      const res = await client.callsQuery({
        project_id: `${entity}/${project}`,
        filter: {
          call_ids: [callId],
        },
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
          'output',
        ],
        include_costs: false,
        include_feedback: false,
      });

      if (res.calls.length > 0) {
        const call = res.calls[0];
        setPolledCall({
          traceCall: call,
        });
        // Update polling state based on latest data
        setShouldPoll(!call.ended_at);
        setError(null);
      }
    } catch (err) {
      setError(err as Error);
      // Continue polling on error
      setShouldPoll(true);
    } finally {
      setLoading(false);
    }
  }, [entity, project, callId, getClient]);

  // Set up polling when the call is running
  useEffect(() => {
    let mounted = true;
    let pollTimeout: NodeJS.Timeout | undefined;

    const poll = async () => {
      if (!mounted) {
        return;
      }
      await fetchCall();

      // Schedule next poll if we should continue polling
      if (mounted && shouldPoll) {
        pollTimeout = setTimeout(poll, pollIntervalMs);
      }
    };

    // Start polling
    poll();

    return () => {
      mounted = false;
      if (pollTimeout) {
        clearTimeout(pollTimeout);
      }
    };
  }, [
    entity,
    project,
    callId,
    pollIntervalMs,
    getClient,
    shouldPoll,
    fetchCall,
  ]);

  // Use polled data once available, fall back to initial call data
  return {
    loading: loading && initialCallResult.loading,
    error,
    result: polledCall || initialCallResult.result,
  };
};
