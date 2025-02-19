import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {Button} from '../../../../../Button';
import * as DropdownMenu from '../../../../../DropdownMenu';
import {Icon} from '../../../../../Icon';
import {Tailwind} from '../../../../../Tailwind';
import {TraceServerClient} from '../wfReactInterface/traceServerClient';
import {useGetTraceServerClientContext} from '../wfReactInterface/traceServerClientContext';
import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {LoadableWithError} from '../wfReactInterface/wfDataModelHooksInterface';

// Types
type ThreadsPageProps = {
  entity: string;
  project: string;
  threadId?: string;
};

type TraceTreeFlat = {
  [callId: string]: {
    id: string;
    parentId?: string;
    childrenIds: string[];
    dfsOrder: number;
    call: TraceCallSchema;
  };
};

// View type definitions
type ThreadViewType = 'list' | 'timeline';
type TraceViewType = 'timeline' | 'tree' | 'table' | 'list';

// Thread Panel Components
const ThreadListView: React.FC<{
  onTraceSelect: (traceId: string) => void;
  traces: string[];
  loading: boolean;
  error: Error | null;
}> = ({onTraceSelect, traces, loading, error}) => {
  if (loading) {
    return <div className="p-4">Loading traces...</div>;
  }
  if (error) {
    return <div className="p-4 text-red-500">Error: {error.message}</div>;
  }
  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">Thread List View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {traces.map(traceId => (
            <Button
              key={traceId}
              variant="ghost"
              onClick={() => onTraceSelect(traceId)}
              className="w-full justify-start">
              <span className="truncate">{traceId}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};

const ThreadTimelineView: React.FC<{
  onTraceSelect: (traceId: string) => void;
  traces: string[];
  loading: boolean;
  error: Error | null;
}> = ({onTraceSelect, traces, loading, error}) => {
  if (loading) {
    return <div className="p-4">Loading traces...</div>;
  }
  if (error) {
    return <div className="p-4 text-red-500">Error: {error.message}</div>;
  }
  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">Thread Timeline View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {traces.map(traceId => (
            <Button
              key={traceId}
              variant="ghost"
              onClick={() => onTraceSelect(traceId)}
              className="w-full justify-start">
              <span className="truncate">{traceId}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};

// Trace Panel Components
const TraceListView: React.FC<{
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}> = ({traceTreeFlat, onCallSelect}) => {
  const sortedCalls = useMemo(() => {
    return Object.values(traceTreeFlat)
      .sort((a, b) => {
        const aStartedAt = Date.parse(a.call.started_at);
        const bStartedAt = Date.parse(b.call.started_at);
        return bStartedAt - aStartedAt;
      });
  }, [traceTreeFlat]);

  return (
    <div className="h-full overflow-hidden">
      <h3 className="p-4 text-lg font-semibold">List View</h3>
      <div className="h-[calc(100%-4rem)] overflow-y-auto px-4">
        <div className="flex flex-col gap-2">
          {sortedCalls.map(({call}) => (
            <Button
              key={call.id}
              variant="ghost"
              onClick={() => onCallSelect(call.id)}
              className="w-full justify-start text-left">
              <div className="flex w-full flex-col gap-1 overflow-hidden">
                <div className="font-medium truncate">
                  {call.display_name || call.op_name}
                </div>
                <div className="text-xs text-moon-500 truncate">
                  Started: {new Date(call.started_at).toLocaleString()}
                  {call.ended_at && ` • Duration: ${
                    ((Date.parse(call.ended_at) - Date.parse(call.started_at)) / 1000).toFixed(2)
                  }s`}
                </div>
              </div>
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};

const TraceTimelineView: React.FC<{
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}> = ({traceTreeFlat, onCallSelect}) => {
  return (
    <div className="p-4">
      <h3 className="mb-4 text-lg font-semibold">Timeline View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in
        timeline
      </pre>
    </div>
  );
};

const TraceTreeView: React.FC<{
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}> = ({traceTreeFlat, onCallSelect}) => {
  return (
    <div className="p-4">
      <h3 className="mb-4 text-lg font-semibold">Tree View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in
        tree
      </pre>
    </div>
  );
};

const TraceTableView: React.FC<{
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}> = ({traceTreeFlat, onCallSelect}) => {
  return (
    <div className="p-4">
      <h3 className="mb-4 text-lg font-semibold">Table View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in
        table
      </pre>
    </div>
  );
};

// Call Detail Panel Components
const CallDetailSection: React.FC<{
  call: TraceCallSchema | undefined;
  sectionTitle: string;
}> = ({call, sectionTitle}) => {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
        <h2 className="text-sm font-semibold truncate">{sectionTitle}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-8">
        {call ? (
          <pre className="text-sm text-moon-500 overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(call, null, 2)}
          </pre>
        ) : (
          <div className="text-moon-500">No call selected</div>
        )}
      </div>
    </div>
  );
};

// Utility functions
const buildTraceTreeFlat = (traceCalls: TraceCallSchema[]): TraceTreeFlat => {
  const traceTreeFlat: TraceTreeFlat = {};
  traceCalls.forEach(call => {
    traceTreeFlat[call.id] = {
      id: call.id,
      parentId: call.parent_id,
      childrenIds: [],
      dfsOrder: 0,
      call,
    };
  });
  traceCalls.forEach(call => {
    if (call.parent_id) {
      traceTreeFlat[call.parent_id].childrenIds.push(call.id);
    }
  });
  const sortFn = (a: string, b: string) => {
    const aCall = traceTreeFlat[a];
    const bCall = traceTreeFlat[b];
    const aStartedAt = Date.parse(aCall.call.started_at);
    const bStartedAt = Date.parse(bCall.call.started_at);
    return aStartedAt - bStartedAt;
  };
  // Sort the children calls by start time
  Object.values(traceTreeFlat).forEach(call => {
    call.childrenIds.sort(sortFn);
  });
  let dfsOrder = 0;
  let stack: string[] = [];
  Object.values(traceTreeFlat).forEach(call => {
    if (call.parentId === null) {
      stack.push(call.id);
    }
  });
  stack.sort(sortFn);
  while (stack.length > 0) {
    const callId = stack.shift();
    if (!callId) {
      continue;
    }
    const call = traceTreeFlat[callId];
    if (call) {
      call.dfsOrder = dfsOrder;
      dfsOrder++;
    }
    stack = [...call.childrenIds, ...stack];
  }
  return traceTreeFlat;
};

// Data Fetch

const useThreadList = (
  entity: string,
  project: string
): LoadableWithError<string[]> => {
  // TODO: Implement this
  return useMemo(() => {
    return {
      loading: false,
      error: null,
      result: ["thread-id-1", "thread-id-2"],
    };
  }, []);
};

const useTracesForThread = (
  entity: string,
  project: string,
  threadId?: string
): LoadableWithError<string[]> => {
  // TODO: Implement this
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
    let mounted = true;
    const client = getClient();
    fetchBareThreadTraces(client, entity, project, threadId).then(res => {
      if (mounted) {
        setTraces(res.map(c => c.trace_id));
        setLoading(false);
      }
    }).catch(err => {
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
      op_names: ["weave:///company-of-agents/mini-lms/op/Agent.go:*"],
    },
    limit: 10,
    sort_by: [{"field":"started_at","direction":"desc"}],
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

const useBareTraceCalls = (
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
    sort_by: [{"field":"started_at","direction":"desc"}],
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

export const ThreadsPage = ({entity, project, threadId}: ThreadsPageProps) => {
  // Global state
  const [selectedThreadId, setSelectedThreadIdDirect] = useState<string | undefined>(threadId);
  const [selectedTraceId, setSelectedTraceIdDirect] = useState<string | undefined>();
  const [selectedCallId, setSelectedCallIdDirect] = useState<string | undefined>();
  console.log({selectedThreadId, selectedTraceId, selectedCallId});

  const setSelectedThreadId = useCallback((threadId: string) => {
    setSelectedThreadIdDirect(threadId);
    setSelectedTraceIdDirect(undefined);
    setSelectedCallIdDirect(undefined);
  }, [setSelectedThreadIdDirect]);

  const setSelectedTraceId = useCallback((traceId: string) => {
    setSelectedTraceIdDirect(traceId);
    setSelectedCallIdDirect(undefined);
  }, [setSelectedTraceIdDirect]);

  const setSelectedCallId = useCallback((callId: string) => {
    setSelectedCallIdDirect(callId);
  }, [setSelectedCallIdDirect]);
  
  // View state
  const [threadView, setThreadView] = useState<ThreadViewType>('list');
  const [traceView, setTraceView] = useState<TraceViewType>('timeline');
  const [isThreadMenuOpen, setIsThreadMenuOpen] = useState(false);

  // Data fetching
  const {
    loading: threadsLoading,
    error: threadsError,
    result: threads,
  } = useThreadList(entity, project);

  const {
    loading: tracesLoading,
    error: tracesError,
    result: traces,
  } = useTracesForThread(entity, project, selectedThreadId);

  const {
    loading: callsLoading,
    error: callsError,
    result: traceCalls,
  } = useBareTraceCalls(entity, project, selectedTraceId);

  // Auto-select first thread when threads load and none is selected
  useEffect(() => {
    if (!selectedThreadId && threads && threads.length > 0 && !threadsLoading && !threadsError) {
      setSelectedThreadId(threads[0]);
    }
  }, [threads, threadsLoading, threadsError, selectedThreadId, setSelectedThreadId]);

  // Auto-select first trace when traces load
  useEffect(() => {
    console.log({traces, tracesLoading, tracesError, selectedTraceId});
    if (!selectedTraceId && traces && traces.length > 0 && !tracesLoading && !tracesError) {
      console.log('auto-selecting trace', traces[0]);
      setSelectedTraceId(traces[0]);
    }
  }, [traces, tracesLoading, tracesError, selectedTraceId, setSelectedTraceId]);

  // Derived data
  const traceTreeFlat = useMemo(
    () => buildTraceTreeFlat(traceCalls ?? []),
    [traceCalls]
  );
  const selectedCall = selectedCallId
    ? traceTreeFlat[selectedCallId]?.call
    : undefined;


  // Render helpers
  const renderThreadView = () => {
    if (!selectedThreadId) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="info" className="mb-2" />
          <p>Select a thread to begin exploring</p>
        </div>
      );
    }

    const props = {
      onTraceSelect: setSelectedTraceId,
      traces: traces ?? [],
      loading: tracesLoading,
      error: tracesError,
    };
    switch (threadView) {
      case 'list':
        return <ThreadListView {...props} />;
      case 'timeline':
        return <ThreadTimelineView {...props} />;
    }
  };

  const renderTraceView = () => {
    if (!selectedThreadId) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="info" className="mb-2" />
          <p>Select a thread to view traces</p>
        </div>
      );
    }

    if (tracesLoading) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="loading" className="mb-2 animate-spin" />
          <p>Loading traces...</p>
        </div>
      );
    }

    if (tracesError) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-red-500">
          <Icon name="warning" className="mb-2" />
          <p>Error loading traces: {tracesError.message}</p>
        </div>
      );
    }

    if (!traces || traces.length === 0) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="info" className="mb-2" />
          <p>No traces found for this thread</p>
        </div>
      );
    }

    if (!selectedTraceId) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="loading" className="mb-2 animate-spin" />
          <p>Selecting trace...</p>
        </div>
      );
    }

    if (callsLoading) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="loading" className="mb-2 animate-spin" />
          <p>Loading trace details...</p>
        </div>
      );
    }

    if (callsError) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-red-500">
          <Icon name="warning" className="mb-2" />
          <p>Error loading trace details: {callsError.message}</p>
        </div>
      );
    }

    const props = {
      traceTreeFlat,
      onCallSelect: setSelectedCallId,
    };
    switch (traceView) {
      case 'timeline':
        return <TraceTimelineView {...props} />;
      case 'tree':
        return <TraceTreeView {...props} />;
      case 'table':
        return <TraceTableView {...props} />;
      case 'list':
        return <TraceListView {...props} />;
    }
  };

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full w-full flex-col overflow-hidden">
        {/* Main Header */}
        <div className="flex h-44 min-h-44 shrink-0 items-center justify-between border-b border-moon-250 px-16">
          <div className="flex items-center gap-8 overflow-hidden">
            <h1 className="text-lg font-semibold truncate">Thread Explorer</h1>
            <DropdownMenu.Root
              open={isThreadMenuOpen}
              onOpenChange={setIsThreadMenuOpen}>
              <DropdownMenu.Trigger>
                <Button 
                  variant="secondary" 
                  icon={threadsLoading ? "loading" : "overflow-vertical"}
                  disabled={threadsLoading || Boolean(threadsError)}
                  className={threadsLoading ? "animate-spin" : ""}>
                  <span className="truncate">
                    {selectedThreadId ? `Thread: ${selectedThreadId}` : 'Select Thread'}
                  </span>
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Content>
                {threadsError ? (
                  <DropdownMenu.Item className="text-red-500">
                    <Icon name="warning" className="mr-2 shrink-0" />
                    <span className="truncate">Error: {threadsError.message}</span>
                  </DropdownMenu.Item>
                ) : threads && threads.length > 0 ? (
                  threads.map(threadId => (
                    <DropdownMenu.Item
                      key={threadId}
                      onSelect={() => {
                        setSelectedThreadId(threadId);
                        setIsThreadMenuOpen(false);
                      }}>
                      <div className="flex w-full items-center gap-2 overflow-hidden">
                        {threadId === selectedThreadId && (
                          <Icon name="checkmark" className="text-green-500 shrink-0" />
                        )}
                        <span className="truncate">{threadId}</span>
                      </div>
                    </DropdownMenu.Item>
                  ))
                ) : (
                  <DropdownMenu.Item disabled>No threads available</DropdownMenu.Item>
                )}
              </DropdownMenu.Content>
            </DropdownMenu.Root>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* Thread Panel - 30% */}
          <div className="flex w-[30%] flex-col overflow-hidden border-r border-moon-250">
            <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="text-sm font-semibold truncate">Thread View</h2>
              <div className="flex items-center gap-2">
                <Button
                  variant={threadView === 'list' ? 'primary' : 'ghost'}
                  onClick={() => setThreadView('list')}
                  icon="list">
                  List
                </Button>
                <Button
                  variant={threadView === 'timeline' ? 'primary' : 'ghost'}
                  onClick={() => setThreadView('timeline')}
                  icon="chart-horizontal-bars">
                  Timeline
                </Button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              {renderThreadView()}
            </div>
          </div>

          {/* Trace Panel - 40% */}
          <div className="flex w-[40%] flex-col overflow-hidden">
            <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="text-sm font-semibold truncate">Trace View</h2>
              <div className="flex items-center gap-2">
                <Button
                  variant={traceView === 'list' ? 'primary' : 'ghost'}
                  onClick={() => setTraceView('list')}
                  icon="list">
                  List
                </Button>
                <Button
                  variant={traceView === 'timeline' ? 'primary' : 'ghost'}
                  onClick={() => setTraceView('timeline')}
                  icon="chart-horizontal-bars">
                  Timeline
                </Button>
                <Button
                  variant={traceView === 'tree' ? 'primary' : 'ghost'}
                  onClick={() => setTraceView('tree')}
                  icon="miller-columns">
                  Tree
                </Button>
                <Button
                  variant={traceView === 'table' ? 'primary' : 'ghost'}
                  onClick={() => setTraceView('table')}
                  icon="table">
                  Table
                </Button>
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              {renderTraceView()}
            </div>
          </div>

          {/* Call Detail Panel - 30% */}
          <div className="flex w-[30%] flex-col overflow-hidden border-l border-moon-250">
            <div className="flex min-h-0 h-full flex-col overflow-hidden">
              <CallDetailSection
                call={selectedCall}
                sectionTitle="Call Details"
              />
              <CallDetailSection
                call={selectedCall}
                sectionTitle="Call Inputs"
              />
              <CallDetailSection
                call={selectedCall}
                sectionTitle="Call Outputs"
              />
            </div>
          </div>
        </div>

        {/* Main Footer */}
        <div className="flex h-32 shrink-0 items-center border-t border-moon-250 px-16">
          <span className="text-sm text-moon-500 truncate">
            {tracesLoading
              ? 'Loading traces...'
              : tracesError
              ? `Error: ${tracesError.message}`
              : selectedThreadId
              ? `Thread: ${selectedThreadId} (${traces?.length ?? 0} traces)`
              : 'No thread selected'}{' '}
            {' | '}
            {callsLoading
              ? 'Loading calls...'
              : callsError
              ? `Error: ${callsError.message}`
              : selectedTraceId
              ? `Trace: ${selectedTraceId} (${
                  Object.keys(traceTreeFlat).length
                } calls)`
              : 'No trace selected'}{' '}
            {' | '}
            {selectedCallId ? `Call: ${selectedCallId}` : 'No call selected'}
          </span>
        </div>
      </div>
    </Tailwind>
  );
};
