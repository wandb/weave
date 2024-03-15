// Handle serialization/deserialization of CG, for remote execution
import _ from 'lodash';

import {StaticOpStore} from '../../opStore/static';
import {opDefIsLowLevel} from '../../runtimeHelpers';
import {isSimpleTypeShape} from '../helpers';
import type {Type} from '../types';
import {constDate, constNodeUnsafe, varNode, voidNode} from './construction';
import type {EditingNode, EditingOp, EditingOutputNode} from './editing';
import {MemoizedHasher} from './editing';
import type {ConstNode, OpInputNodes, VarNode, VoidNode} from './types';

type NodeId = string;
type SerializedRef = number;
interface NormExecGraph {
  ops: Map<NodeId, {ref: SerializedRef; op: EditingOp}>;
  constNodes: Map<NodeId, {ref: SerializedRef; node: ConstNode}>;
  varNodes: Map<NodeId, {ref: SerializedRef; node: VarNode}>;
  voidNodes: Map<NodeId, {ref: SerializedRef; node: VoidNode}>;
  outputNodes: Map<NodeId, {ref: SerializedRef; node: EditingOutputNode}>;
}

// Batched version of above; batching allows us to retain and share node
// identity among graphs
export interface BatchedNormExecGraphs {
  ng: NormExecGraph;
  roots: Set<EditingNode>;
}

// The serialized forms of each node type.
// Serialized forms roughly match non-serialized structure but
// replace node references with a number (SerializedRef)
interface SerializedConst {
  nodeType: 'const';
  type:
    | Type
    | {
        type: 'function';
        inputTypes: Record<string, Type>;
        outputType: Type;
      }
    | {type: 'list'; objectType: Type};
  val: any;
}

interface SerializedOp {
  inputs: Record<string, SerializedRef>;
  name: string;
}

interface SerializedVar {
  nodeType: 'var';
  type: string;
  varName: string;
}

interface SerializedVoid {
  nodeType: 'void';
}

interface SerializedOutput {
  nodeType: 'output';
  fromOp: SerializedRef;
  type:
    | Type
    | {
        type: 'function';
        inputTypes: Record<string, Type>;
        outputType: Type;
      }
    | {type: 'list'; objectType: Type};
  id: string;
}

type SerializedNode =
  | SerializedOp
  | SerializedConst
  | SerializedVar
  | SerializedVoid
  | SerializedOutput;

type SerializableGraph = {
  constNodes: Record<string, SerializedConst>;
  outputNodes: Record<string, SerializedOutput>;
  varNodes: Record<string, SerializedVar>;
  voidNodes: Record<string, SerializedVoid>;
  ops: Record<string, SerializedOp>;
};

function isSerializedOp(x: any): x is SerializedOp {
  return typeof x.name !== 'undefined';
}

// Final data structure before JSON serialization
export type FlatSerializableGraph = SerializedNode[];

export interface BatchedGraphs {
  // Misleading, this may actually be multiple disconnected subgraphs, but the naive TS type
  // is indistinguishable
  nodes: FlatSerializableGraph;
  targetNodes: SerializedRef[];
}

// TODO(np): Leaving this here because it competes with graphNorm, and is not used by anything
// else.  If we need this outside of serialization, extract it.
// Mostly copied from graphNorm.ts, except this operates on Types.Node not CGTypes.EditingNode
// and correctly handles constFunction to include the inner fn's ops
class GraphNormalizer {
  private nextId: SerializedRef = 0;
  private ng: NormExecGraph | null = null;
  private roots: Set<EditingNode> = new Set();
  private hasher = new MemoizedHasher();

  public normalize(node: EditingNode): NormExecGraph {
    this.reset();
    this.visitNode(node);
    return this.ng!;
  }

  public normalizeBatch(nodes: EditingNode[]): BatchedNormExecGraphs {
    this.reset();
    for (const node of nodes) {
      // TODO(np): This should really be an ordered set
      this.roots.add(node);
      this.visitNode(node);
    }
    return {
      ng: this.ng!,
      roots: new Set(this.roots),
    };
  }

  private reset() {
    this.nextId = 0;
    this.ng = {
      ops: new Map(),
      constNodes: new Map(),
      varNodes: new Map(),
      voidNodes: new Map(),
      outputNodes: new Map(),
    };
    this.roots.clear();
  }

  private visitOp(op: EditingOp) {
    const hashId = this.hasher.opId(op);
    const opId = this.ng!.ops.get(hashId);
    if (opId != null) {
      return;
    }
    const id = this.nextId++;
    this.ng!.ops.set(hashId, {ref: id, op});
    for (const argNode of Object.values(op.inputs)) {
      this.visitNode(argNode);
    }
    return;
  }

  private visitNode(node: EditingNode) {
    const hashId = this.hasher.nodeId(node);
    if (node.nodeType === 'const') {
      const nodeRef = this.ng!.constNodes.get(hashId);
      if (nodeRef != null) {
        return;
      }
      const id = this.nextId++;
      this.ng!.constNodes.set(hashId, {ref: id, node});
      if (typeof node.type === 'object' && node.type.type === 'function') {
        this.visitNode(node.val);
      }
      return;
    } else if (node.nodeType === 'var') {
      const nodeRef = this.ng!.varNodes.get(hashId);
      if (nodeRef != null) {
        return;
      }
      const id = this.nextId++;
      this.ng!.varNodes.set(hashId, {ref: id, node});
      return;
    } else if (node.nodeType === 'void') {
      const nodeRef = this.ng!.voidNodes.get(hashId);
      if (nodeRef != null) {
        return;
      }
      const id = this.nextId++;
      this.ng!.voidNodes.set(hashId, {ref: id, node});
      return;
    } else if (node.nodeType === 'output') {
      const nodeRef = this.ng!.outputNodes.get(hashId);
      if (nodeRef != null) {
        return;
      }
      const id = this.nextId++;
      this.ng!.outputNodes.set(hashId, {ref: id, node});
      this.visitOp(node.fromOp);
      return;
    }
    throw new Error(`invalid node: ${JSON.stringify(node)}`);
  }
}

// Given a normalized exec graph, look up node/op and return its serialized ref, if any
function lookup(
  hasher: MemoizedHasher,
  norm: NormExecGraph,
  nodeOrOp: EditingNode | EditingOp
): SerializedRef | undefined {
  if (typeof (nodeOrOp as EditingOp).name !== 'undefined') {
    const op = nodeOrOp as EditingOp;
    const hashId = hasher.opId(op);
    return norm.ops.get(hashId)?.ref;
  } else {
    const node = nodeOrOp as EditingNode;
    const hashId = hasher.nodeId(node);
    switch (node.nodeType) {
      case 'const':
        return norm.constNodes.get(hashId)?.ref;
      case 'output':
        return norm.outputNodes.get(hashId)?.ref;
      case 'var':
        return norm.varNodes.get(hashId)?.ref;
      case 'void':
        return norm.voidNodes.get(hashId)?.ref;
    }
  }
}

// Convert SerializableGraph into the final wire format, a flat, sorted array of nodes
function flattenGraph(graph: SerializableGraph): FlatSerializableGraph {
  return [
    ...Object.entries(graph.constNodes),
    ...Object.entries(graph.outputNodes),
    ...Object.entries(graph.varNodes),
    ...Object.entries(graph.voidNodes),
    ...Object.entries(graph.ops),
  ]
    .sort((a, b) => parseInt(a[0], 10) - parseInt(b[0], 10))
    .map(entry => entry[1]);
}

// Array of CG -> Normalized Graph -> Serializable Graph + Roots -> Flat Serializable Graph
export function serialize(graphs: EditingNode[]): BatchedGraphs {
  const hasher = new MemoizedHasher();
  const norm = new GraphNormalizer().normalizeBatch(graphs);

  const localLookup = (node: EditingNode | EditingOp) =>
    lookup(hasher, norm.ng, node);

  const inverse: SerializableGraph = {
    ops: Object.fromEntries(
      Array.from(norm.ng.ops).map(([hid, {op, ref}]) => {
        const result = {name: op.name, inputs: {}} as any;
        for (const inputName of Object.keys(op.inputs)) {
          result.inputs[inputName] = localLookup(op.inputs[inputName]);
        }
        return [ref, result];
      })
    ) as Record<string, SerializedOp>,
    constNodes: Object.fromEntries(
      Array.from(norm.ng.constNodes).map(([hid, {node, ref}]) => {
        const result = {
          nodeType: node.nodeType,
          type: node.type,
          val: null,
        } as any;
        if (
          node.val !== null &&
          typeof node.val === 'object' &&
          !_.isArray(node.val)
        ) {
          if (node.val.nodeType === 'output') {
            result.val = {
              nodeType: node.val.nodeType,
              fromOp: localLookup(node.val.fromOp),
            };
          } else {
            if (node.val instanceof Date) {
              result.val = {type: 'date', val: node.val};
            } else {
              result.val = node.val;
            }
          }
        } else {
          result.val = node.val;
        }
        return [ref, result];
      })
    ) as Record<string, SerializedConst>,
    varNodes: Object.fromEntries(
      Array.from(norm.ng.varNodes).map(([hid, {node, ref}]) => {
        return [ref, node];
      })
    ) as Record<string, SerializedVar>,
    voidNodes: Object.fromEntries(
      Array.from(norm.ng.voidNodes).map(([hid, {node, ref}]) => {
        return [ref, node];
      })
    ) as Record<string, SerializedVoid>,
    outputNodes: Object.fromEntries(
      Array.from(norm.ng.outputNodes).map(([hid, {node, ref}]) => {
        const result: SerializedOutput = {
          nodeType: node.nodeType,
          fromOp: localLookup(node.fromOp) as number, // TODO(np): TS calculates the wrong type here
          type: node.type,
          id: hasher.typedNodeId(node),
        };
        return [ref, result];
      })
    ) as Record<string, SerializedOutput>,
  };

  return {
    nodes: flattenGraph(inverse),
    targetNodes: graphs.map(rootNode => {
      const ref = localLookup(rootNode)!;
      if (typeof ref === 'undefined') {
        throw new Error(`cannot find node ${JSON.stringify(rootNode)}`);
      }
      return ref;
    }),
  };
}

const expensiveOpNames = new Set([
  'get',
  'set',
  // Marking `getReturnType` and `Ref-type` as inexpensive for now so that the
  // weave app can bundle them into the same graph. This is typically used to
  // determine the combined column type, so it should be done in one shot. This
  // is a short term optimization until we have the new object store.
  // 'getReturnType',
  // 'Ref-type',
  'ref',
]);

// Heuristic to determine if an op is expensive. We should merge
// all subgraphs with non-expensive ops into a single graph, since
// the network latency will dominate the cost.

const opIsExpensive = (op: EditingOp): boolean => {
  const opName = op.name;
  if (expensiveOpNames.has(opName)) {
    return true;
  } else if (opName.startsWith('root-')) {
    return true;
  } else if (opName.includes('refine')) {
    return true;
  } else if (opName.includes('panel')) {
    return true;
  }
  return false;
};

// Given an array of graph entry points, produce an array of disjoint subgraphs
function getDisjointGraphs(
  graphs: EditingNode[],
  mergeInexpensiveOps: boolean = false
): [EditingNode[][], number[][]] {
  const hasher = new MemoizedHasher();
  const nodeSubgraphMap: Map<string | EditingNode, number> = new Map();
  const subgraphSet = (node: EditingNode, subgraph: number) => {
    const key = node.nodeType === 'output' ? hasher.nodeId(node) : node;
    nodeSubgraphMap.set(key, subgraph);
  };
  const subgraphGet = (node: EditingNode) => {
    const key = node.nodeType === 'output' ? hasher.nodeId(node) : node;
    return nodeSubgraphMap.get(key);
  };
  const expensiveSubgraphs: Set<number> = new Set();

  let currentSubgraph = 0;
  let nextSubgraph = 1;

  function markSubgraph(node: EditingNode, subgraph: number) {
    subgraphSet(node, subgraph);
    if (node.nodeType === 'output') {
      if (opIsExpensive(node.fromOp)) {
        expensiveSubgraphs.add(subgraph);
      }
      Object.values(node.fromOp.inputs).forEach(input => {
        markSubgraph(input, subgraph);
      });
    }
  }

  // Return true if we've encountered an existing subgraph
  function walkAndCheck(node: EditingNode, root: EditingNode): boolean {
    const existingSubgraph = subgraphGet(node);
    if (existingSubgraph != null) {
      // encountered an existing subgraph, assign root and its descendants to existing subgraph
      markSubgraph(root, existingSubgraph);
      return true;
    }

    // Otherwise, assign node to current subgraph
    subgraphSet(node, currentSubgraph);

    // Recurse into inputs
    if (node.nodeType === 'output') {
      if (opIsExpensive(node.fromOp)) {
        expensiveSubgraphs.add(currentSubgraph);
      }
      for (const input of Object.values(node.fromOp.inputs)) {
        if (walkAndCheck(input, root)) {
          return true;
        }
      }
    }

    return false;
  }

  // Walk graphs and assign subgraphs
  for (const graph of graphs) {
    if (!walkAndCheck(graph, graph)) {
      currentSubgraph = nextSubgraph++;
    }
  }

  // Build result
  const result: EditingNode[][] = [];
  const originalIndexes: number[][] = [];
  for (let i = 0; i < graphs.length; i++) {
    const graph = graphs[i];
    const subgraph = subgraphGet(graph)!;
    if (result[subgraph] == null) {
      result[subgraph] = [];
      originalIndexes[subgraph] = [];
    }
    result[subgraph].push(graph);
    originalIndexes[subgraph].push(i);
  }

  if (mergeInexpensiveOps) {
    let inexpensiveSubgraph = -1;
    for (let i = 0; i < result.length; i++) {
      if (!expensiveSubgraphs.has(i)) {
        if (inexpensiveSubgraph === -1) {
          inexpensiveSubgraph = i;
        } else {
          // Merge subgraph i into inexpensiveSubgraph
          result[inexpensiveSubgraph].push(...result[i]);
          originalIndexes[inexpensiveSubgraph].push(...originalIndexes[i]);
          result[i] = [];
          originalIndexes[i] = [];
        }
      }
    }
  }

  return [result, originalIndexes];
}

export function serializeMulti(
  graphs: EditingNode[],
  mergeInexpensiveOps: boolean = false
): [BatchedGraphs[], number[][]] {
  // Serialize graphs into disjoint BatchedGraphs
  const [disjointGraphs, originalIndexes] = getDisjointGraphs(
    graphs,
    mergeInexpensiveOps
  );
  return [disjointGraphs.map(serialize), originalIndexes];
}

// Serialized Graph -> Flat Serializable Graph -> CG
export function deserialize(batch: BatchedGraphs): EditingNode[] {
  const nodeCache = new Map<SerializedNode, EditingNode>();
  const cached = (
    serializedNode: SerializedNode,
    node: EditingNode
  ): EditingNode => {
    nodeCache.set(serializedNode, node);
    return node;
  };

  const doDeserialize = (node: SerializedNode): EditingNode => {
    if (nodeCache.has(node)) {
      return nodeCache.get(node)!;
    }
    if (isSerializedOp(node)) {
      const opDef = StaticOpStore.getInstance().getOpDef(node.name);
      if (opDefIsLowLevel(opDef)) {
        return cached(
          node,
          opDef.op(
            _.mapValues(node.inputs, o =>
              doDeserialize(batch.nodes[o])
            ) as OpInputNodes<any>
          )
        );
      }
    } else if (node.nodeType === 'const') {
      if (isSimpleTypeShape(node.type)) {
        switch (node.type) {
          case 'date':
            return cached(node, constDate(node.val.val));
          default:
            return cached(node, node);
        }
      } else {
        // function or other complex type
        switch (node.type.type) {
          case 'function':
            const fnNode = doDeserialize(batch.nodes[node.val.fromOp]);
            return cached(node, constNodeUnsafe(node.type, fnNode));
          default:
            return cached(node, constNodeUnsafe(node.type, node.val));
        }
      }
    } else if (node.nodeType === 'var') {
      return cached(node, varNode(node.type as Type, node.varName));
    } else if (node.nodeType === 'void') {
      return voidNode();
    } else if (node.nodeType === 'output') {
      const fromOp = batch.nodes[node.fromOp];
      if (!isSerializedOp(fromOp)) {
        throw new Error(`invalid graph: Expected op at index ${node.fromOp}`);
      }
      const opDef = StaticOpStore.getInstance().getOpDef(fromOp.name);
      if (opDefIsLowLevel(opDef)) {
        const result = opDef.op(
          _.mapValues(fromOp.inputs, o =>
            doDeserialize(batch.nodes[o])
          ) as OpInputNodes<any>
        );
        result.id = node.id;
        result.type = node.type;
        return cached(node, result);
      }
    }
    throw new Error(`Can't handle node: ${JSON.stringify(node)}`);
  };

  return batch.targetNodes.map(ref => doDeserialize(batch.nodes[ref]));
}

// Actually we're just going to try to deserialize the thing and report errors
export function isSerializedGraph(
  maybeGraph: any
): maybeGraph is FlatSerializableGraph {
  if (!_.isArray(maybeGraph)) {
    return false;
  }
  try {
    deserialize({nodes: maybeGraph, targetNodes: [0]});
  } catch (err) {
    return false;
  }
  return true;
}
