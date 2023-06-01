import {Hasher, MemoizedHasher} from '../../model/graph/editing/hash';
import * as GraphTypes from '../../model/graph/types';
import {ForwardGraphStorage, ForwardOp} from './types';

export class HashingStorage implements ForwardGraphStorage {
  private hash: Hasher;
  private roots = new Set<ForwardOp>();
  private ops = new Map<string, ForwardOp>();

  public constructor() {
    this.hash = new MemoizedHasher();
  }

  getRoots(): Set<ForwardOp> {
    return this.roots;
  }

  getOp(op: GraphTypes.Op): ForwardOp | undefined {
    return this.ops.get(this.hash.opId(op));
  }

  setOp(op: ForwardOp) {
    this.ops.set(this.hash.opId(op.op), op);
  }

  size() {
    return this.ops.size;
  }
}
