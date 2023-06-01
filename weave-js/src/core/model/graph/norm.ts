import {EditingNode, EditingOp, EditingOutputNode} from './editing/types';
import {ConstNode, VarNode, VoidNode} from './types';

let globalId = 0;

export interface NormGraph {
  ops: Map<EditingOp, number>;
  voidNodes: Map<VoidNode, number>;
  constNodes: Map<ConstNode, number>;
  varNodes: Map<VarNode, number>;
  outputNodes: Map<EditingOutputNode, number>;
}

function visitOp(ng: NormGraph, op: EditingOp): number {
  const opId = ng.ops.get(op);
  if (opId != null) {
    return opId;
  }
  const id = globalId++;
  ng.ops.set(op, id);
  for (const argNode of Object.values(op.inputs)) {
    visitNode(ng, argNode);
  }
  return id;
}

function visitNode(ng: NormGraph, node: EditingNode): number {
  if (node.nodeType === 'const') {
    const nodeId = ng.constNodes.get(node);
    if (nodeId != null) {
      return nodeId;
    }
    const id = globalId++;
    ng.constNodes.set(node, id);
    return id;
  } else if (node.nodeType === 'var') {
    const nodeId = ng.varNodes.get(node);
    if (nodeId != null) {
      return nodeId;
    }
    const id = globalId++;
    ng.varNodes.set(node, id);
    return id;
  } else if (node.nodeType === 'output') {
    const nodeId = ng.outputNodes.get(node);
    if (nodeId != null) {
      return nodeId;
    }
    const id = globalId++;
    ng.outputNodes.set(node, id);
    visitOp(ng, node.fromOp);
    return id;
  } else if (node.nodeType === 'void') {
    const nodeId = ng.voidNodes.get(node);
    if (nodeId != null) {
      return nodeId;
    }
    const id = globalId++;
    ng.voidNodes.set(node, id);
    return id;
  }
  throw new Error('graphNorm: unknown node type');
}

export function graphNorm(node: EditingNode) {
  // TODO: do we need to use WeakMap to avoid leaks?
  const ng: NormGraph = {
    ops: new Map(),
    constNodes: new Map(),
    varNodes: new Map(),
    outputNodes: new Map(),
    voidNodes: new Map(),
  };
  visitNode(ng, node);
  return ng;
}
