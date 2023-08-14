import _ from 'lodash';

import type {EditingNode, EditingOp} from './types';

// TODO: is this unique enough for now?
const cyrb53 = (str: string, seed = 0) => {
  /* tslint:disable:no-bitwise */
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0, ch; i < str.length; i++) {
    ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 =
    Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^
    Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 =
    Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^
    Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 4294967296 * (2097151 & h2) + (h1 >>> 0);
  /* tslint:enable:no-bitwise */
};

export function hash(str: string): string {
  return cyrb53(str).toString();
}

export interface Hasher {
  typedNodeId(node: EditingNode): string;
  nodeId(node: EditingNode): string;
  opId(op: EditingOp): string;
}

export class MemoizedHasher implements Hasher {
  public typedNodeId: MemoizedHasher['_typedNodeId'] & _.MemoizedFunction;
  public nodeId: MemoizedHasher['_nodeId'] & _.MemoizedFunction;

  public opId: MemoizedHasher['_opId'] & _.MemoizedFunction;

  public constructor() {
    this.typedNodeId = _.memoize(this._typedNodeId.bind(this));
    this.nodeId = _.memoize(this._nodeId.bind(this));
    this.opId = _.memoize(this._opId.bind(this));
  }

  public clear() {
    this.typedNodeId.cache.clear?.();
    this.nodeId.cache.clear?.();
    this.opId.cache.clear?.();
  }

  // Note: We include types for nodes! This is so that
  // e.g. Maybe<string> and Maybe<number> that are both none values resolve
  // to different IDs. Since nodeID is used in the node refinement path
  // (e.g libexp), its important to include type information.
  //
  // We can have a different version of this that ignores types for
  // execution time if we want. Types can be large objects and hashing them
  // may be somewhat expensive. On the other hand, at the const nodes, types
  // will be small, and we should have fewer output nodes.
  private _typedNodeId(node: EditingNode): string {
    if (node.nodeType === 'const') {
      // TODO: think about what to do with function types. Right now we'll hash
      // the json representation of the graph there (which includes types).
      return hash(JSON.stringify({type: node.type, val: node.val}));
    } else if (node.nodeType === 'output') {
      // important nodeId of an output op == opId of the op we came from
      return hash(
        JSON.stringify({
          name: node.fromOp.name,
          type: node.type,
          inputs: _.mapValues(node.fromOp.inputs, this.typedNodeId),
        })
      );
    } else if (node.nodeType === 'var') {
      return hash(JSON.stringify(node));
    } else if (node.nodeType === 'void') {
      return 'void';
    }

    console.error('nodeId not valid for node', node);
    throw new Error('invalid: nodeId not valid for node');
  }

  /** Produce a stable ID for a node.
   *
   * A node's ID will change if the expression leading to that node changes.
   */
  private _nodeId(node: EditingNode): string {
    if (node.nodeType === 'const') {
      // TODO: think about what to do with function types. Right now we'll hash
      // the json representation of the graph there (which includes types).
      return hash(JSON.stringify(node));
    } else if (node.nodeType === 'output') {
      // important nodeId of an output op == opId of the op we came from
      return this.opId(node.fromOp);
    } else if (node.nodeType === 'var') {
      return hash(JSON.stringify(node));
    } else if (node.nodeType === 'void') {
      return 'void';
    }
    console.error('nodeId not valid for node', node);
    throw new Error('invalid: nodeId not valid for node');
  }

  private _opId(op: EditingOp): string {
    return hash(
      JSON.stringify({
        name: op.name,
        inputs: _.mapValues(op.inputs, this.typedNodeId),
      })
    );
  }
}
