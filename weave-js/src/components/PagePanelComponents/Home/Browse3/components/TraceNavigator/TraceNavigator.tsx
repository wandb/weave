import {Button} from '@wandb/weave/components/Button';
import {Loading} from '@wandb/weave/components/Loading';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {TableRowSelectionContext} from '../../../TableRowSelectionContext';
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

  useUpdateTableRowSelectionContextPath(
    stack,
    focusedCallId,
    traceTreeFlatRootedAtRootCallId,
    traceTreeFlatRootedAtTraceRoot
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
        <h2 className="truncate text-sm font-semibold">Trace view</h2>
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
                    variant="ghost"
                    active={traceViewId === view.id}
                    onClick={() => setTraceViewId(view.id)}
                    icon={view.icon}
                    size="small"
                    disabled={isDisabled}
                  />
                }
              />
            );
          })}
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-hidden">
        <div className="flex h-full flex-col">
          {loading ? (
            <div className="flex h-full w-full items-center justify-center">
              <Loading />
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

  const buildAncestorStackForCall = React.useCallback(
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

      return stack;
    },
    [traceTreeFlat]
  );

  const buildDescendantStackForCall = React.useCallback(
    (callId: string) => {
      if (!callId || Object.keys(traceTreeFlat).length === 0) {
        return [];
      }

      // Build stack down to leaves
      const stack: string[] = [];
      let currentId = callId;
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
        const currIndex = curr.indexOf(selectedCallId);
        const ancestorStack = buildAncestorStackForCall(selectedCallId);
        let descendantStack = buildDescendantStackForCall(selectedCallId);
        if (currIndex !== -1) {
          descendantStack = curr.slice(currIndex + 1);
        }
        return ancestorStack.concat(descendantStack);
      });
    } else {
      setStackState([]);
    }
  }, [selectedCallId, buildAncestorStackForCall, buildDescendantStackForCall]);

  return stackState;
};

const useUpdateTableRowSelectionContextPath = (
  stack: string[],
  focusedCallId: string | undefined,
  traceTreeFlatRootedAtRootCallId: TraceTreeFlat,
  traceTreeFlatRootedAtTraceRoot: TraceTreeFlat
) => {
  // Update the selection path when the focused call changes - this is used by the
  // trace table to maintain sub-selection of the root call
  const {setGetDescendantCallIdAtSelectionPath} = useContext(
    TableRowSelectionContext
  );

  const selectionPath = useMemo(() => {
    if (!focusedCallId) {
      return undefined;
    }
    const focusIndex = stack.findIndex(id => id === focusedCallId);
    if (focusIndex <= 0) {
      return undefined;
    }
    const focusStack = stack.slice(1, focusIndex + 1);
    const getIndexWithinSameNameSiblings = (
      parentCallId: string,
      childCallId: string
    ) => {
      const parentCall = traceTreeFlatRootedAtTraceRoot[parentCallId];
      const childrenIds = parentCall.childrenIds;
      const filteredChildren = childrenIds.filter(
        id =>
          traceTreeFlatRootedAtTraceRoot[id]?.call.op_name ===
          traceTreeFlatRootedAtTraceRoot[childCallId]?.call.op_name
      );
      const orderedChildren = filteredChildren.sort((a, b) => {
        return (
          traceTreeFlatRootedAtTraceRoot[a].dfsOrder -
          traceTreeFlatRootedAtTraceRoot[b].dfsOrder
        );
      });
      return orderedChildren.findIndex(id => id === childCallId);
    };

    const path: Array<{name: string; index: number}> = [];
    let parentId: string | undefined;
    focusStack.forEach(id => {
      path.push({
        name: traceTreeFlatRootedAtTraceRoot[id].call.op_name,
        index: parentId ? getIndexWithinSameNameSiblings(parentId, id) : 0,
      });
      parentId = id;
    });
    return path;
  }, [focusedCallId, stack, traceTreeFlatRootedAtTraceRoot]);

  const getDescendantCallIdAtSelectionPath = useCallback(
    (callId: string) => {
      // Validate callId is in the trace
      let targetCall: TraceTreeFlat[string] | undefined =
        traceTreeFlatRootedAtTraceRoot[callId];
      if (!targetCall || !selectionPath) {
        return null;
      }
      selectionPath.forEach(part => {
        if (!targetCall) {
          return;
        }
        const childrenIds = targetCall.childrenIds;
        const childrenCalls = childrenIds.map(
          id => traceTreeFlatRootedAtTraceRoot[id]
        );
        const filteredChildren = childrenCalls.filter(
          child => child?.call.op_name === part.name
        );
        const sortedChildren = filteredChildren.sort((a, b) => {
          return a.dfsOrder - b.dfsOrder;
        });
        if (part.index > sortedChildren.length) {
          targetCall = undefined;
          return;
        } else {
          targetCall = sortedChildren[part.index];
        }
      });

      return targetCall?.id;
    },
    [selectionPath, traceTreeFlatRootedAtTraceRoot]
  );

  useEffect(() => {
    setGetDescendantCallIdAtSelectionPath?.(getDescendantCallIdAtSelectionPath);
  }, [
    getDescendantCallIdAtSelectionPath,
    setGetDescendantCallIdAtSelectionPath,
  ]);
};
