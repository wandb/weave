import {TraceCallSchema} from '../../../pages/wfReactInterface/traceServerClientTypes';
import {parseSpanName} from '../../../pages/wfReactInterface/tsDataModelHooks';
import {TraceTreeFlat} from './types';

/**
 * Builds a flattened representation of a trace call tree.
 * This is the core data structure used throughout the application for representing
 * and navigating trace calls.
 *
 * Key features:
 * - Maps call IDs to their node information for O(1) lookup
 * - Maintains parent-child relationships for tree traversal
 * - Assigns DFS ordering for consistent display and navigation
 * - Preserves all call metadata for display and analysis
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

  const sortCalls = (a: TraceCallSchema, b: TraceCallSchema) => {
    const aStartedAt = Date.parse(a.started_at);
    const bStartedAt = Date.parse(b.started_at);
    return aStartedAt - bStartedAt;
  };

  // Sort children by start time for consistent ordering
  const sortFn = (a: string, b: string) => {
    const aCall = traceTreeFlat[a];
    const bCall = traceTreeFlat[b];
    return sortCalls(aCall.call, bCall.call);
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
  rootCalls.sort((a, b) => sortCalls(a.call, b.call));

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

/**
 * Represents a node in the visualization tree
 */
export interface VisTreeNode {
  id: string;
  label: string;
  children: VisTreeNode[];
  level: number;
  // Metadata useful for visualization
  size?: number; // Size of this subtree (number of descendants + 1)
  depth?: number; // Max depth of this subtree
  parentId?: string; // Reference to parent for easier traversal
  metadata?: {
    startTime: string;
    endTime?: string;
    duration?: number;
    status?: string;
    type?: string;
  };
}

/**
 * Represents a node in the code structure map.
 * This is used to transform the execution trace into a logical code structure view.
 */
export interface CodeMapNode {
  /** The operation name (key for this node) */
  opName: string;
  /** Child operations in the code structure */
  children: CodeMapNode[];
  /** All trace call IDs that map to this operation */
  callIds: string[];
}

/**
 * Transforms a trace tree into a code structure map.
 * This collapses the execution trace into a unique operation tree,
 * representing the actual code structure rather than the execution flow.
 *
 * Key features:
 * - Collapses multiple calls to the same operation into a single node
 * - Maintains the logical structure of the code
 * - Preserves references to all calls for each operation
 * - Handles recursive calls by reusing existing nodes
 *
 * @param traceTreeFlat The flattened trace tree to transform
 * @returns An array of root CodeMapNodes representing the code structure
 */
export const buildCodeMap = (traceTreeFlat: TraceTreeFlat): CodeMapNode[] => {
  // Helper to find a node in the ancestor chain or peer group
  const findExistingOp = (
    opName: string,
    current: CodeMapNode,
    ancestors: CodeMapNode[]
  ): CodeMapNode | null => {
    // Check ancestors first
    const ancestorMatch = ancestors.find(a => a.opName === opName);
    if (ancestorMatch) {
      return ancestorMatch;
    }

    // Check peers (siblings of current node)
    const currentParent = ancestors[ancestors.length - 1];
    if (currentParent) {
      const peerMatch = currentParent.children.find(c => c.opName === opName);
      if (peerMatch) {
        return peerMatch;
      }
    }

    return null;
  };

  // Process a trace node at its target location in the code map
  const processNode = (
    callId: string,
    target: CodeMapNode,
    ancestors: CodeMapNode[]
  ) => {
    const node = traceTreeFlat[callId];
    if (!node) {
      return;
    }

    // Add this call to the target operation
    target.callIds.push(callId);

    // Process all children
    node.childrenIds.forEach(childId => {
      const childNode = traceTreeFlat[childId];
      if (!childNode) {
        return;
      }

      const childOpName = parseSpanName(childNode.call.op_name);

      // Find if this operation exists in ancestors or peers
      const existingOp = findExistingOp(childOpName, target, [
        ...ancestors,
        target,
      ]);

      if (existingOp) {
        // Operation exists, process child at that location
        processNode(
          childId,
          existingOp,
          existingOp === target
            ? ancestors
            : ancestors.includes(existingOp)
            ? ancestors.slice(0, ancestors.indexOf(existingOp) + 1)
            : [...ancestors, target]
        );
      } else {
        // New operation, create it as child of target
        const newOp: CodeMapNode = {
          opName: childOpName,
          children: [],
          callIds: [],
        };
        target.children.push(newOp);
        processNode(childId, newOp, [...ancestors, target]);
      }
    });
  };

  // Start with root nodes
  const rootMap = new Map<string, CodeMapNode>();

  Object.values(traceTreeFlat)
    .filter(node => !node.parentId || !traceTreeFlat[node.parentId])
    .forEach(node => {
      const opName = parseSpanName(node.call.op_name);

      // Get or create root operation
      let rootOp = rootMap.get(opName);
      if (!rootOp) {
        rootOp = {
          opName,
          children: [],
          callIds: [],
        };
        rootMap.set(opName, rootOp);
      }

      // Process the node at this root operation
      processNode(node.id, rootOp, []);
    });

  return Array.from(rootMap.values());
};

/**
 * Generates a consistent color for a given operation name.
 * Uses a simple but effective string hash that avoids bitwise operations.
 */
export const getColorForOpName = (opName: string): string => {
  // Use a simple string hash that sums char codes
  let hash = 0;
  for (let i = 0; i < opName.length; i++) {
    hash = Math.abs(hash * 31 + opName.charCodeAt(i));
  }

  // Use a more muted color palette
  // - Lower saturation (40% instead of 70%)
  // - Higher lightness (75% instead of 50%)
  // - Rotate hue to favor blue/purple/green spectrum
  const hue = (hash % 270) + 180; // Range from 180-450 (wraps around to 90), favoring cool colors
  return `hsl(${hue}, 40%, 75%)`;
};

/**
 * Formats a duration in milliseconds to a human-readable string
 */
export const formatDuration = (ms: number): string => {
  if (ms < 1000) {
    return `${ms.toFixed(0)}ms`;
  }
  return `${(ms / 1000).toFixed(2)}s`;
};

/**
 * Formats a timestamp to a human-readable string
 */
export const formatTimestamp = (timestamp: string): string => {
  return new Date(timestamp).toLocaleString();
};

export const getCallDisplayName = (call: TraceCallSchema): string => {
  return call.display_name || parseSpanName(call.op_name);
};
