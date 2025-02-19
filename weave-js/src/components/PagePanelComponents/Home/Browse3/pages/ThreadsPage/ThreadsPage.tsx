import React, {useEffect, useMemo, useState} from 'react';

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
  }
}

// View type definitions
type ThreadViewType = 'list' | 'timeline';
type TraceViewType = 'timeline' | 'tree' | 'table';

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
    <div className="p-4">
      <h3 className="text-lg font-semibold mb-4">Thread List View</h3>
      <div className="flex flex-col gap-2">
        {traces.map(traceId => (
          <Button
            key={traceId}
            variant="ghost"
            onClick={() => onTraceSelect(traceId)}
            className="justify-start">
            {traceId}
          </Button>
        ))}
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
    <div className="p-4">
      <h3 className="text-lg font-semibold mb-4">Thread Timeline View</h3>
      <div className="flex flex-col gap-2">
        {traces.map(traceId => (
          <Button
            key={traceId}
            variant="ghost"
            onClick={() => onTraceSelect(traceId)}
            className="justify-start">
            {traceId}
          </Button>
        ))}
      </div>
    </div>
  );
};

// Trace Panel Components
const TraceTimelineView: React.FC<{
  traceTreeFlat: TraceTreeFlat;
  onCallSelect: (callId: string) => void;
}> = ({traceTreeFlat, onCallSelect}) => {
  return (
    <div className="p-4">
      <h3 className="text-lg font-semibold mb-4">Timeline View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in timeline
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
      <h3 className="text-lg font-semibold mb-4">Tree View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in tree
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
      <h3 className="text-lg font-semibold mb-4">Table View</h3>
      <pre className="text-sm text-moon-500">
        {JSON.stringify(Object.keys(traceTreeFlat).length, null, 2)} calls in table
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
    <div className="flex flex-1 flex-col">
      <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
        <h2 className="text-sm font-semibold">{sectionTitle}</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-8">
        {call ? (
          <pre className="text-sm text-moon-500">
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
      call: call,
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

const useTracesForThread = (
  entity: string,
  project: string,
  threadId: string
): LoadableWithError<string[]> => {
  // TODO: Implement this
  return useMemo(() => ({
    loading: false,
    error: null,
    result: ['0194bf80-6587-7780-96bb-c275b21f1f5d'],
  }), []);
};

const useBareTraceCalls = (
  entity: string,
  project: string,
  traceId: string
): LoadableWithError<TraceCallSchema[]> => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [traceCalls, setTraceCalls] = useState<TraceCallSchema[]>([]);
  const getClient = useGetTraceServerClientContext();

  useEffect(() => {
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
  const [selectedThreadId, setSelectedThreadId] = useState<string | undefined>(threadId);
  const [selectedTraceId, setSelectedTraceId] = useState<string | undefined>();
  const [selectedCallId, setSelectedCallId] = useState<string | undefined>();

  // View state
  const [threadView, setThreadView] = useState<ThreadViewType>('list');
  const [traceView, setTraceView] = useState<TraceViewType>('timeline');
  const [isThreadMenuOpen, setIsThreadMenuOpen] = useState(false);

  // Data fetching
  const {
    loading: tracesLoading,
    error: tracesError,
    result: traces,
  } = useTracesForThread(entity, project, selectedThreadId ?? '');

  const {
    loading: callsLoading,
    error: callsError,
    result: traceCalls,
  } = useBareTraceCalls(entity, project, selectedTraceId ?? '');

  // Derived data
  const traceTreeFlat = useMemo(() => buildTraceTreeFlat(traceCalls ?? []), [traceCalls]);
  const selectedCall = selectedCallId ? traceTreeFlat[selectedCallId]?.call : undefined;

  // Effect to clear downstream selections when parent selection changes
  useEffect(() => {
    setSelectedTraceId(undefined);
    setSelectedCallId(undefined);
  }, [selectedThreadId]);

  useEffect(() => {
    setSelectedCallId(undefined);
  }, [selectedTraceId]);

  // Render helpers
  const renderThreadView = () => {
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
    if (!selectedTraceId) {
      return <div className="p-4 text-moon-500">Select a trace to view details</div>;
    }
    if (callsLoading) {
      return <div className="p-4">Loading...</div>;
    }
    if (callsError) {
      return <div className="p-4 text-red-500">Error: {callsError.message}</div>;
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
    }
  };

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full w-full flex-col">
        {/* Main Header */}
        <div className="min-h-44 flex h-44 items-center justify-between border-b border-moon-250 px-16">
          <div className="flex items-center gap-8">
            <h1 className="text-lg font-semibold">Thread Explorer</h1>
            <DropdownMenu.Root
              open={isThreadMenuOpen}
              onOpenChange={setIsThreadMenuOpen}>
              <DropdownMenu.Trigger>
                <Button variant="secondary" icon="overflow-vertical">
                  Select Thread
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Content>
                <DropdownMenu.Item>Thread 1</DropdownMenu.Item>
                <DropdownMenu.Item>Thread 2</DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Root>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex flex-1 overflow-hidden">
          {/* Thread Panel - 30% */}
          <div className="flex flex-[3] flex-col border-r border-moon-250">
            <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="text-sm font-semibold">Thread View</h2>
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
            <div className="flex-1 overflow-y-auto">
              {renderThreadView()}
            </div>
          </div>

          {/* Trace Panel - 40% */}
          <div className="flex flex-[4] flex-col">
            <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="text-sm font-semibold">Trace View</h2>
              <div className="flex items-center gap-2">
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
            <div className="flex-1 overflow-y-auto">
              {renderTraceView()}
            </div>
          </div>

          {/* Call Detail Panel - 30% */}
          <div className="flex flex-[3] flex-col border-l border-moon-250">
            <div className="flex h-full flex-col">
              <CallDetailSection call={selectedCall} sectionTitle="Call Details" />
              <CallDetailSection call={selectedCall} sectionTitle="Call Inputs" />
              <CallDetailSection call={selectedCall} sectionTitle="Call Outputs" />
            </div>
          </div>
        </div>

        {/* Main Footer */}
        <div className="flex h-32 items-center border-t border-moon-250 px-16">
          <span className="text-sm text-moon-500">
            {tracesLoading ? 'Loading traces...' : 
              tracesError ? `Error: ${tracesError.message}` :
              selectedThreadId ? `Thread: ${selectedThreadId} (${traces?.length ?? 0} traces)` : 
              'No thread selected'} {' | '}
            {callsLoading ? 'Loading calls...' : 
              callsError ? `Error: ${callsError.message}` :
              selectedTraceId ? `Trace: ${selectedTraceId} (${Object.keys(traceTreeFlat).length} calls)` : 
              'No trace selected'} {' | '}
            {selectedCallId ? `Call: ${selectedCallId}` : 'No call selected'}
          </span>
        </div>
      </div>
    </Tailwind>
  );
};