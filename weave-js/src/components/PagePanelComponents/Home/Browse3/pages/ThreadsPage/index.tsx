import React, {useEffect, useState} from 'react';

import {Button} from '../../../../../Button';
import * as DropdownMenu from '../../../../../DropdownMenu';
import {Icon} from '../../../../../Icon';
import {Tailwind} from '../../../../../Tailwind';
import {TraceNavigator} from '../../components/TraceNavigator/TraceNavigator';
import {useWFHooks} from '../wfReactInterface/context';
import {useThreadList, useTraceRootsForThread} from './hooks';
import {ThreadsPageProps} from './types';
import {
  callViews,
  getCallView,
  getThreadView,
  threadViews,
} from './viewRegistry';

interface CallViewWrapperProps {
  entity: string;
  project: string;
  callId: string;
  viewId: string;
}

const CallViewWrapper: React.FC<CallViewWrapperProps> = ({
  entity,
  project,
  callId,
  viewId,
}) => {
  const {useCall} = useWFHooks();
  const {loading, result} = useCall({
    entity,
    project,
    callId,
  });

  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-moon-500">
        <Icon name="loading" className="mb-2 animate-spin" />
        <p>Loading call details...</p>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="flex h-full flex-col items-center justify-center text-red-500">
        <Icon name="warning" className="mb-2" />
        <p>Error loading call details: Call not found</p>
      </div>
    );
  }

  const CallViewComponent = getCallView(viewId).component;
  return <CallViewComponent call={result} />;
};

export const ThreadsPage = ({entity, project, threadId}: ThreadsPageProps) => {
  // Global state
  const [selectedThreadId, setSelectedThreadId] = useState<string | undefined>(
    threadId
  );
  const [selectedTraceId, setSelectedTraceId] = useState<string | undefined>();
  const [selectedCallId, setSelectedCallId] = useState<string | undefined>();

  // View state
  const [threadViewId, setThreadViewId] = useState(threadViews[0].id);
  const [isThreadMenuOpen, setIsThreadMenuOpen] = useState(false);
  const [callViewId, setCallViewId] = useState(callViews[0].id);

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
  } = useTraceRootsForThread(
    entity,
    project,
    selectedThreadId,
    threadViewId === 'connected' ? 2000 : 0 // Poll every 2 seconds for connected view
  );

  // const {
  //   loading: callsLoading,
  //   error: callsError,
  //   result: traceCalls,
  // } = useBareTraceCalls(entity, project, selectedTraceId);

  // Clear downstream selections when thread changes or starts loading
  useEffect(() => {
    setSelectedTraceId(undefined);
    setSelectedCallId(undefined);
  }, [selectedThreadId, tracesLoading]);

  // Clear call selection when trace changes or starts loading
  useEffect(() => {
    setSelectedCallId(undefined);
  }, [selectedTraceId]);
  // }, [selectedTraceId, callsLoading]);

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

  // Auto-select first trace when traces load and none is selected
  useEffect(() => {
    if (
      !selectedTraceId &&
      traces &&
      traces.length > 0 &&
      !tracesLoading &&
      !tracesError
    ) {
      setSelectedTraceId(traces[0].trace_id);
    }
  }, [traces, tracesLoading, tracesError, selectedTraceId, setSelectedTraceId]);

  // Derived data
  // const traceTreeFlat = useMemo(
  //   () => buildTraceTreeFlat(traceCalls ?? []),
  //   [traceCalls]
  // );

  // // Auto-select first call when trace tree is built and no call is selected
  // useEffect(() => {
  //   const treeEntries = Object.entries(traceTreeFlat);
  //   if (
  //     !selectedCallId &&
  //     treeEntries.length > 0 &&
  //     !callsLoading &&
  //     !callsError
  //   ) {
  //     // Find the call with the lowest dfsOrder (root of the trace)
  //     const [firstCallId] = treeEntries.reduce((acc, [id, node]) =>
  //       node.dfsOrder < acc[1].dfsOrder ? [id, node] : acc
  //     );
  //     setSelectedCallId(firstCallId);
  //   }
  // }, [
  //   traceTreeFlat,
  //   callsLoading,
  //   callsError,
  //   selectedCallId,
  //   setSelectedCallId,
  // ]);

  // Only show call details if we have valid data and aren't loading
  // const showCallDetails =
  //   !callsLoading &&
  //   !callsError &&
  //   selectedCallId &&
  //   traceTreeFlat[selectedCallId];
  // const selectedCall = showCallDetails
  //   ? traceTreeFlat[selectedCallId]?.call
  //   : undefined;

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

    const ThreadViewComponent = getThreadView(threadViewId).component;
    return (
      <ThreadViewComponent
        onTraceSelect={setSelectedTraceId}
        traceRoots={traces ?? []}
        selectedTraceId={selectedTraceId}
        loading={tracesLoading}
        error={tracesError}
        onThreadSelect={setSelectedThreadId}
      />
    );
  };

  const renderCallDetails = () => {
    // if (callsLoading) {
    //   return (
    //     <div className="flex h-full flex-col items-center justify-center text-moon-500">
    //       <Icon name="loading" className="mb-2 animate-spin" />
    //       <p>Loading call details...</p>
    //     </div>
    //   );
    // }

    // if (callsError) {
    //   return (
    //     <div className="flex h-full flex-col items-center justify-center text-red-500">
    //       <Icon name="warning" className="mb-2" />
    //       <p>Error loading call details: {callsError.message}</p>
    //     </div>
    //   );
    // }

    if (!selectedCallId) {
      return (
        <div className="flex h-full flex-col items-center justify-center text-moon-500">
          <Icon name="info" className="mb-2" />
          <p>Select a call to view details</p>
        </div>
      );
    }

    return (
      <CallViewWrapper
        entity={entity}
        project={project}
        callId={selectedCallId}
        viewId={callViewId}
      />
    );
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
                  icon={threadsLoading ? undefined : 'overflow-vertical'}
                  disabled={threadsLoading || Boolean(threadsError)}>
                  <div className="flex items-center">
                    {threadsLoading ? (
                      <Icon name="loading" className="mr-2 animate-spin" />
                    ) : null}
                    <span className="truncate">
                      {selectedThreadId
                        ? `Thread: ${selectedThreadId}`
                        : 'Select Thread'}
                    </span>
                  </div>
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
              <div className="flex items-center gap-3">
                {threadViews.map(view => (
                  <Button
                    key={view.id}
                    variant={threadViewId === view.id ? 'primary' : 'ghost'}
                    onClick={() => setThreadViewId(view.id)}
                    icon={view.icon}
                    size="small"
                    className="!p-3"
                    title={view.label}>
                    <span className="sr-only">{view.label}</span>
                  </Button>
                ))}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-hidden">
              {renderThreadView()}
            </div>
          </div>

          {/* Trace Panel - 40% */}
          <div className="flex w-[40%] flex-col overflow-hidden">
            {selectedTraceId ? (
              <TraceNavigator
                entity={entity}
                project={project}
                selectedTraceId={selectedTraceId}
                selectedCallId={selectedCallId}
                setSelectedCallId={setSelectedCallId}
              />
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-moon-500">
                <Icon name="info" className="mb-2" />
                <p>Select a trace to view details</p>
              </div>
            )}
          </div>

          {/* Call Detail Panel - 30% */}
          <div className="flex w-[30%] flex-col overflow-hidden border-l border-moon-250">
            <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="truncate text-sm font-semibold">Call View</h2>
              <div className="flex items-center gap-3">
                {callViews.map(view => (
                  <Button
                    key={view.id}
                    variant={callViewId === view.id ? 'primary' : 'ghost'}
                    onClick={() => setCallViewId(view.id)}
                    icon={view.icon}
                    size="small"
                    className="!p-3"
                    title={view.label}>
                    <span className="sr-only">{view.label}</span>
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex h-full min-h-0 flex-col overflow-hidden">
              {renderCallDetails()}
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
            {selectedTraceId
              ? `Trace: ${selectedTraceId}`
              : 'No trace selected'}{' '}
            {' | '}
            {selectedCallId ? `Call: ${selectedCallId}` : 'No call selected'}
          </span>
        </div>
      </div>
    </Tailwind>
  );
};
