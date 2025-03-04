import {Button} from '@wandb/weave/components/Button';
import React, {useEffect, useMemo, useState} from 'react';

import {useBareTraceCalls} from '../../pages/wfReactInterface/tsDataModelHooksTraces';
import TraceScrubber from './TraceScrubber';
import {StackBreadcrumb} from './TraceScrubber/components/StackBreadcrumb';
import {getTraceView, traceViews} from './traceViewRegistry';
import {StackState, TraceTreeFlat} from './TraceViews/types';
import {buildTraceTreeFlat} from './TraceViews/utils';

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

  const stack = useStackForCallId(traceTreeFlat, selectedCallId);

  const childProps = useMemo(
    () => ({
      traceTreeFlat,
      selectedCallId,
      onCallSelect: setSelectedCallId,
      stack,
    }),
    [traceTreeFlat, selectedCallId, setSelectedCallId, stack]
  );

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
            <>
              <StackBreadcrumb {...childProps} />
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex-1 overflow-auto">
                  <TraceViewComponent {...childProps} />
                </div>
                {getTraceView(traceViewId).showScrubber && (
                  <TraceScrubber {...childProps} />
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const useStackForCallId = (
  traceTreeFlat: TraceTreeFlat,
  selectedCallId: string | undefined
) => {
  const [stackState, setStackState] = React.useState<StackState>([]);

  const buildStackForCall = React.useCallback(
    (callId: string) => {
      if (!callId) {
        return [];
      }
      const stack: string[] = [];
      let currentId = callId;

      // Build stack up to root
      while (currentId) {
        stack.unshift(currentId);
        const node = traceTreeFlat[currentId];
        if (!node) {
          break;
        }
        currentId = node.parentId || '';
      }

      // Build stack down to leaves
      currentId = callId;
      while (currentId) {
        const node = traceTreeFlat[currentId];
        if (!node || node.childrenIds.length === 0) {
          break;
        }
        // Take the first child in chronological order
        const nextId = [...node.childrenIds].sort(
          (a, b) =>
            Date.parse(traceTreeFlat[a].call.started_at) -
            Date.parse(traceTreeFlat[b].call.started_at)
        )[0];
        stack.push(nextId);
        currentId = nextId;
      }

      return stack;
    },
    [traceTreeFlat]
  );

  // Update stack state whenever selected call changes
  React.useEffect(() => {
    if (selectedCallId) {
      setStackState(curr => {
        if (!curr.includes(selectedCallId)) {
          return buildStackForCall(selectedCallId);
        }
        return curr;
      });
    } else {
      setStackState([]);
    }
  }, [selectedCallId, buildStackForCall]);

  return stackState;
};
