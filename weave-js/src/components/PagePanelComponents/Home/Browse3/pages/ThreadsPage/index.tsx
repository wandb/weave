import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {Button} from '../../../../../Button';
import * as DropdownMenu from '../../../../../DropdownMenu';
import {Icon} from '../../../../../Icon';
import {Tailwind} from '../../../../../Tailwind';
import {CallDetailSection} from './components/CallDetailSection';
import {ThreadListView, ThreadTimelineView} from './components/ThreadViews';
import {
  TraceListView,
  TraceTableView,
  TraceTimelineView,
  TraceTreeView,
} from './components/TraceViews';
import {useBareTraceCalls, useThreadList, useTracesForThread} from './hooks';
import {ThreadsPageProps, ThreadViewType, TraceViewType} from './types';
import {buildTraceTreeFlat} from './utils';

export const ThreadsPage = ({entity, project, threadId}: ThreadsPageProps) => {
  // Global state
  const [selectedThreadId, setSelectedThreadIdDirect] = useState<
    string | undefined
  >(threadId);
  const [selectedTraceId, setSelectedTraceIdDirect] = useState<
    string | undefined
  >();
  const [selectedCallId, setSelectedCallIdDirect] = useState<
    string | undefined
  >();

  const setSelectedThreadId = useCallback((newThreadId: string) => {
    setSelectedThreadIdDirect(newThreadId);
    setSelectedTraceIdDirect(undefined);
    setSelectedCallIdDirect(undefined);
  }, []);

  const setSelectedTraceId = useCallback((newTraceId: string) => {
    setSelectedTraceIdDirect(newTraceId);
    setSelectedCallIdDirect(undefined);
  }, []);

  const setSelectedCallId = useCallback((newCallId: string) => {
    setSelectedCallIdDirect(newCallId);
  }, []);

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
    if (
      !selectedThreadId &&
      threads &&
      threads.length > 0 &&
      !threadsLoading &&
      !threadsError
    ) {
      setSelectedThreadId(threads[0]);
    }
  }, [
    threads,
    threadsLoading,
    threadsError,
    selectedThreadId,
    setSelectedThreadId,
  ]);

  // Auto-select first trace when traces load
  useEffect(() => {
    if (
      !selectedTraceId &&
      traces &&
      traces.length > 0 &&
      !tracesLoading &&
      !tracesError
    ) {
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
        <div className="min-h-44 flex h-44 shrink-0 items-center justify-between border-b border-moon-250 px-16">
          <div className="flex items-center gap-8 overflow-hidden">
            <h1 className="truncate text-lg font-semibold">Thread Explorer</h1>
            <DropdownMenu.Root
              open={isThreadMenuOpen}
              onOpenChange={setIsThreadMenuOpen}>
              <DropdownMenu.Trigger>
                <Button
                  variant="secondary"
                  icon={threadsLoading ? 'loading' : 'overflow-vertical'}
                  disabled={threadsLoading || Boolean(threadsError)}
                  className={threadsLoading ? 'animate-spin' : ''}>
                  <span className="truncate">
                    {selectedThreadId
                      ? `Thread: ${selectedThreadId}`
                      : 'Select Thread'}
                  </span>
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Content>
                {threadsError ? (
                  <DropdownMenu.Item className="text-red-500">
                    <Icon name="warning" className="mr-2 shrink-0" />
                    <span className="truncate">
                      Error: {threadsError.message}
                    </span>
                  </DropdownMenu.Item>
                ) : threads && threads.length > 0 ? (
                  threads.map(mappedThreadId => (
                    <DropdownMenu.Item
                      key={mappedThreadId}
                      onSelect={() => {
                        setSelectedThreadId(mappedThreadId);
                        setIsThreadMenuOpen(false);
                      }}>
                      <div className="flex w-full items-center gap-2 overflow-hidden">
                        {mappedThreadId === selectedThreadId && (
                          <Icon
                            name="checkmark"
                            className="shrink-0 text-green-500"
                          />
                        )}
                        <span className="truncate">{mappedThreadId}</span>
                      </div>
                    </DropdownMenu.Item>
                  ))
                ) : (
                  <DropdownMenu.Item disabled>
                    No threads available
                  </DropdownMenu.Item>
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
              <h2 className="truncate text-sm font-semibold">Thread View</h2>
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
              <h2 className="truncate text-sm font-semibold">Trace View</h2>
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
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
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
          <span className="truncate text-sm text-moon-500">
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
