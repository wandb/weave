import {TraceCallSchema} from '../wfReactInterface/traceServerClientTypes';
import {TraceTreeFlat} from './types';

/**
 * Builds a flattened representation of a trace call tree.
 *
 * The resulting structure:
 * - Maps call IDs to their node information
 * - Maintains parent-child relationships
 * - Assigns DFS ordering for consistent display
 * - Preserves all call metadata
 *
 * @param traceCalls - Array of trace calls to build the tree from
 * @returns Flattened tree structure with parent-child relationships
 */
export const buildTraceTreeFlat = (
  traceCalls: TraceCallSchema[]
): TraceTreeFlat => {
  // First pass: Create nodes and store basic information
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

  // Second pass: Build parent-child relationships
  traceCalls.forEach(call => {
    if (call.parent_id && traceTreeFlat[call.parent_id]) {
      traceTreeFlat[call.parent_id].childrenIds.push(call.id);
    }
  });

  // Sort children by start time for consistent ordering
  const sortFn = (a: string, b: string) => {
    const aCall = traceTreeFlat[a];
    const bCall = traceTreeFlat[b];
    const aStartedAt = Date.parse(aCall.call.started_at);
    const bStartedAt = Date.parse(bCall.call.started_at);
    return aStartedAt - bStartedAt;
  };

  // Sort all children arrays
  Object.values(traceTreeFlat).forEach(node => {
    node.childrenIds.sort(sortFn);
  });

  // Perform DFS to assign ordering
  let dfsOrder = 0;
  const rootCalls = Object.values(traceTreeFlat).filter(
    node => !node.parentId || !traceTreeFlat[node.parentId]
  );

  // Sort root calls by start time
  rootCalls.sort(
    (a, b) => Date.parse(a.call.started_at) - Date.parse(b.call.started_at)
  );

  // Process each tree in order
  let stack = rootCalls.map(node => node.id);
  while (stack.length > 0) {
    const callId = stack.shift();
    if (!callId) {
      continue;
    }

    const node = traceTreeFlat[callId];
    if (!node) {
      continue;
    }

    // Assign order and add children to stack
    node.dfsOrder = dfsOrder++;
    stack = [...node.childrenIds, ...stack];
  }

  return traceTreeFlat;
};
