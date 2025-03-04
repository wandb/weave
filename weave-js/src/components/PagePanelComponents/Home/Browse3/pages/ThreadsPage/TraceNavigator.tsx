import {Button} from '@wandb/weave/components/Button';
import React, {useEffect, useMemo, useState} from 'react';

import {TraceScrubber} from './components/TraceViews/TraceScrubber';
import {StackBreadcrumb} from './components/TraceViews/TraceScrubber/components/StackBreadcrumb';
import {StackContextProvider} from './components/TraceViews/TraceScrubber/context';
import {useBareTraceCalls} from './hooks';
import {buildTraceTreeFlat} from './utils';
import {getTraceView, traceViews} from './viewRegistry';

export const TraceNavigator = ({
  entity,
  project,
  selectedTraceId,
  selectedCallId,
  setSelectedCallId,
}: {
  entity: string;
  project: string;
  selectedTraceId: string;
  selectedCallId: string | undefined;
  setSelectedCallId: (callId: string) => void;
}) => {
  const {
    loading: traceCallsLoading,
    error: traceCallsError,
    result: traceCalls,
  } = useBareTraceCalls(entity, project, selectedTraceId);

  // Derived data
  const traceTreeFlat = useMemo(
    () => buildTraceTreeFlat(traceCalls ?? []),
    [traceCalls]
  );

  // Auto-select first call when trace tree is built and no call is selected
  useEffect(() => {
    const treeEntries = Object.entries(traceTreeFlat);
    if (
      !selectedCallId &&
      treeEntries.length > 0 &&
      !traceCallsLoading &&
      !traceCallsError
    ) {
      // Find the call with the lowest dfsOrder (root of the trace)
      const [firstCallId] = treeEntries.reduce((acc, [id, node]) =>
        node.dfsOrder < acc[1].dfsOrder ? [id, node] : acc
      );
      setSelectedCallId(firstCallId);
    }
  }, [
    selectedCallId,
    setSelectedCallId,
    traceCallsError,
    traceCallsLoading,
    traceTreeFlat,
  ]);

  const [traceViewId, setTraceViewId] = useState(traceViews[0].id);
  const TraceViewComponent = getTraceView(traceViewId).component;
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
        <h2 className="truncate text-sm font-semibold">Trace View</h2>
        <div className="flex items-center gap-3">
          {traceViews.map(view => (
            <Button
              key={view.id}
              variant={traceViewId === view.id ? 'primary' : 'ghost'}
              onClick={() => setTraceViewId(view.id)}
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
        <div className="flex h-full flex-col">
          {Object.keys(traceTreeFlat).length > 0 && (
            <StackContextProvider
              traceTreeFlat={traceTreeFlat}
              selectedCallId={selectedCallId}>
              <StackBreadcrumb
                traceTreeFlat={traceTreeFlat}
                selectedCallId={selectedCallId}
                onCallSelect={setSelectedCallId}
              />
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex-1 overflow-auto">
                  <TraceViewComponent
                    traceTreeFlat={traceTreeFlat}
                    selectedCallId={selectedCallId}
                    onCallSelect={setSelectedCallId}
                  />
                </div>
                {getTraceView(traceViewId).showScrubber && (
                  <TraceScrubber
                    traceTreeFlat={traceTreeFlat}
                    selectedCallId={selectedCallId}
                    onCallSelect={setSelectedCallId}
                  />
                )}
              </div>
            </StackContextProvider>
          )}
        </div>
      </div>
    </div>
  );
};
