import * as _ from 'lodash';

import {isFunctionLiteral, mapNodes} from './callers';
import * as HL from './hl';
import {EditingNode, EditingOp, Node, pushFrame, Stack, Type} from './model';
import {
  filePathToType,
  list,
  parseArtifactRef,
  typedDict,
  union,
} from './model';
import type {OpStore} from './opStore';

/**
 * We may have a `runs.index(var('x'))` in the executableNode graph.
 * For example, PanelTable column select expressions always contain
 * `index(var('x'))` during editing, to indicate that the expression
 * will be applied to all rows in the table's underlying array.
 * Here we replace `runs.index(var('x'))` with `runs.flatten().limit(10)`. Which
 * means the resulting type will be a union of the summary types
 * for the first 10 runs in the array.
 *
 * We may just want to do this in HL.refineNode all the time. But we can't
 * import ops into HL, that would create a cycle. We'll need a bigger refactor
 */
export const replaceInputVariables = (runNode: Node, opStore: OpStore) => {
  return mapNodes(
    runNode,

    checkNode => {
      if (
        checkNode.nodeType === 'output' &&
        // Look for index ops
        checkNode.fromOp.name === 'index' &&
        // Using a variable for the index argument
        checkNode.fromOp.inputs.index.nodeType === 'var'
      ) {
        return HL.callOpValid(
          'limit',
          {
            arr: HL.callOpValid(
              'flatten',
              {arr: checkNode.fromOp.inputs.arr as any},
              opStore
            ),
            limit: {nodeType: 'const', type: 'number', val: 10},
          },
          opStore
        );
      }
      return checkNode;
    }
  ) as Node;
};

/**
 * Get the frame (the available variables) at `targetNodeOrOp`. This will be the
 * frame provided to the root of the expression, plus any frames added by function
 * literals in which the node was nested. e.g. for node _ in
 *
 * arr.filter(row => _)
 *
 * the frame would be {arr, row} (assuming that arr was provided at the root). For
 * the tail node of the same expression, the frame would only include {arr}.
 *
 * Returns null if the node is not found in `graph`.
 */
export function getStackAtNodeOrOp(
  graph: EditingNode,
  targetNodeOrOp: EditingNode | EditingOp,
  parentStack: Stack,
  opStore: OpStore
): Stack | null {
  if (graph === targetNodeOrOp) {
    return parentStack;
  }

  if (isFunctionLiteral(graph)) {
    return getStackAtNodeOrOp(graph.val, targetNodeOrOp, parentStack, opStore);
  }

  if (graph.nodeType === 'output') {
    //  are we targeting this output's Op?
    if (graph.fromOp === targetNodeOrOp) {
      // if so, we have the frame we want:
      return parentStack;
    }

    const inputNames = Object.keys(graph.fromOp.inputs);
    // recurse into each of the inputs of this operation
    for (const inputName of inputNames) {
      const input = graph.fromOp.inputs[inputName];

      if (isFunctionLiteral(input)) {
        const functionBodyFrame = HL.getFunctionFrame(
          graph.fromOp.name,
          graph.fromOp.inputs[inputNames[0]],
          parentStack,
          opStore
        );
        const childStack = pushFrame(parentStack, functionBodyFrame);
        const foundFrameInFunctionBody = getStackAtNodeOrOp(
          input,
          targetNodeOrOp,
          childStack,
          opStore
        );

        if (foundFrameInFunctionBody !== null) {
          return foundFrameInFunctionBody;
        }

        continue;
      }

      const foundFrame = getStackAtNodeOrOp(
        input,
        targetNodeOrOp,
        parentStack,
        opStore
      );

      if (foundFrame !== null) {
        return foundFrame;
      }
    }
  }

  return null;
}

const isTableTypeHistoryKeyType = (id: string) => {
  return ['table-file', 'partitioned-table', 'joined-table'].includes(id);
};

export const jsValToCGType = (val: any): Type => {
  if (val == null) {
    return 'none';
  } else if (typeof val === 'string') {
    return 'string';
  } else if (typeof val === 'number') {
    return 'number';
  } else if (typeof val === 'boolean') {
    return 'boolean';
  } else if (Array.isArray(val)) {
    return list(union(val.map(v => jsValToCGType(v))));
  } else if (isTableTypeHistoryKeyType(val._type)) {
    // Handle the case of artifact files in summary.
    // TODO: handle more than table-file
    if (val.artifact_path != null) {
      return filePathToType(parseArtifactRef(val.artifact_path).assetPath);
    } else {
      return filePathToType(val.path);
    }
  } else if (val._type === 'wb_trace_tree') {
    return {
      type: 'wb_trace_tree' as const,
    };
  } else if (typeof val === 'object') {
    return typedDict(_.mapValues(val, v => jsValToCGType(v)) as any);
  } else {
    return 'unknown';
  }
};
