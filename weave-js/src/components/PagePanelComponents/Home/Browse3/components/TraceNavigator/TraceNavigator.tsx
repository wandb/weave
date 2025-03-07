import {Button} from '@wandb/weave/components/Button';
import {LoadingDots} from '@wandb/weave/components/LoadingDots';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {FC, useEffect, useMemo, useState} from 'react';

import {useBareTraceCalls} from '../../pages/wfReactInterface/tsDataModelHooksTraces';
import {StackBreadcrumb} from './TraceScrubber/components/StackBreadcrumb';
import {getTraceView, traceViews} from './traceViewRegistry';
import {StackState, TraceTreeFlat, TraceViewProps} from './TraceViews/types';
import {buildTraceTreeFlat} from './TraceViews/utils';

export const TraceNavigator = ({
  entity,
  project,
  traceId,
  focusedCallId,
  setFocusedCallId,
  setRootCallId,
  rootCallId,
}: {
  entity: string;
  project: string;
  traceId: string;
  focusedCallId: string | undefined;
  setFocusedCallId: (callId: string) => void;
  setRootCallId: (callId: string) => void;
  rootCallId: string | undefined;
}) => {
  const {
    loading: traceCallsLoading,
    error: traceCallsError,
    result: traceCalls,
  } = useBareTraceCalls(entity, project, traceId);

  // Derived data
  const traceTreeFlatRootedAtTraceRoot = useMemo(
    () => buildTraceTreeFlat(traceCalls ?? []),
    [traceCalls]
  );

  const traceRootCallId = useMemo(() => {
    const treeEntries = Object.entries(traceTreeFlatRootedAtTraceRoot);
    if (treeEntries.length > 0 && !traceCallsLoading && !traceCallsError) {
      // Find the call with the lowest dfsOrder (root of the trace)
      return treeEntries.reduce((acc, [id, node]) =>
        node.dfsOrder < acc[1].dfsOrder ? [id, node] : acc
      )[0];
    }
    return undefined;
  }, [traceCallsError, traceCallsLoading, traceTreeFlatRootedAtTraceRoot]);

  const rootParentId = useMemo(() => {
    if (!rootCallId) {
      return undefined;
    }
    const currentNode = traceTreeFlatRootedAtTraceRoot[rootCallId];
    return currentNode?.parentId;
  }, [rootCallId, traceTreeFlatRootedAtTraceRoot]);

  const traceTreeFlatRootedAtRootCallId = useMemo(() => {
    if (!rootCallId || traceRootCallId === rootCallId) {
      return traceTreeFlatRootedAtTraceRoot;
    }

    const rootCall = traceTreeFlatRootedAtTraceRoot[rootCallId];
    if (!rootCall) {
      return traceTreeFlatRootedAtTraceRoot;
    }

    const traceTreeFlat: TraceTreeFlat = {};

    const addNode = (node: TraceTreeFlat[string]) => {
      traceTreeFlat[node.call.id] = node;
      node.childrenIds.forEach(nodeId => {
        addNode(traceTreeFlatRootedAtTraceRoot[nodeId]);
      });
    };

    addNode({
      ...rootCall,
      parentId: undefined,
    });

    return traceTreeFlat;
  }, [rootCallId, traceRootCallId, traceTreeFlatRootedAtTraceRoot]);

  // If the focusedCallId is not a descendant of the rootCallId, set it to the rootCallId
  useEffect(() => {
    if (!focusedCallId) {
      return;
    }
    let candidateRootCallId: string | undefined = focusedCallId;
    while (candidateRootCallId) {
      if (candidateRootCallId === rootCallId) {
        return;
      }
      candidateRootCallId =
        traceTreeFlatRootedAtRootCallId[candidateRootCallId]?.parentId;
    }

    setRootCallId(focusedCallId);
  }, [
    focusedCallId,
    rootCallId,
    setRootCallId,
    traceTreeFlatRootedAtRootCallId,
  ]);

  // Auto-select first call when trace tree is built and no call is selected
  useEffect(() => {
    if (!focusedCallId && traceRootCallId) {
      setFocusedCallId(traceRootCallId);
    }
  }, [focusedCallId, setFocusedCallId, traceRootCallId]);

  const stack = useStackForCallId(
    traceTreeFlatRootedAtRootCallId,
    focusedCallId
  );

  const childProps = useMemo(
    () => ({
      traceRootCallId,
      traceTreeFlat: traceTreeFlatRootedAtRootCallId,
      focusedCallId,
      setFocusedCallId,
      setRootCallId,
      stack,
      rootCallId,
      rootParentId,
    }),
    [
      traceRootCallId,
      traceTreeFlatRootedAtRootCallId,
      focusedCallId,
      setFocusedCallId,
      setRootCallId,
      stack,
      rootCallId,
      rootParentId,
    ]
  );

  return <TraceNavigatorInner {...childProps} />;
};

export const TraceNavigatorInner: FC<
  TraceViewProps & {
    traceRootCallId: string | undefined;
    rootParentId: string | undefined;
  }
> = props => {
  const [traceViewId, setTraceViewId] = useState(traceViews[0].id);
  const TraceViewComponent = getTraceView(traceViewId).component;
  const loading = props.traceTreeFlat[props.focusedCallId ?? ''] == null;

  // Count total traces
  const traceCount = Object.keys(props.traceTreeFlat).length;

  // If current view becomes disabled, switch to tree view
  useEffect(() => {
    const currentView = getTraceView(traceViewId);
    if (currentView.maxTraces && traceCount > currentView.maxTraces) {
      setTraceViewId(traceViews[0].id);
    }
  }, [traceCount, traceViewId]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="flex h-32 shrink-0 items-center justify-between border-b border-moon-250 px-8">
        <h2 className="truncate text-sm font-semibold">Trace View</h2>
        <div className="flex items-center gap-3">
          {traceViews.map(view => {
            const isDisabled = !!(
              view.maxTraces && traceCount > view.maxTraces
            );
            const tooltipContent = isDisabled
              ? `${view.label} view is disabled (maximum ${view.maxTraces} traces)`
              : view.label;

            return (
              <Tooltip
                key={view.id}
                content={tooltipContent}
                trigger={
                  <Button
                    variant={'ghost'}
                    active={traceViewId === view.id}
                    onClick={() => setTraceViewId(view.id)}
                    icon={view.icon}
                    size="small"
                    disabled={isDisabled}></Button>
                }></Tooltip>
            );
          })}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full flex-col">
          {loading ? (
            <div className="flex h-full w-full items-center justify-center">
              <LoadingDots />
            </div>
          ) : (
            <>
              <StackBreadcrumb
                {...props}
                rootParentId={props.rootParentId}
                traceRootCallId={props.traceRootCallId}
              />
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="flex-1 overflow-auto">
                  <TraceViewComponent {...props} />
                </div>
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
      if (!callId || Object.keys(traceTreeFlat).length === 0) {
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
      setStackState(buildStackForCall(selectedCallId));
    } else {
      setStackState([]);
    }
  }, [selectedCallId, buildStackForCall]);

  return stackState;
};
