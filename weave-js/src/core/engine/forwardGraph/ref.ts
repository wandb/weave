import * as GraphTypes from '../../model/graph/types';
import {ForwardGraphStorage, ForwardOp} from './types';

export class RefStorage implements ForwardGraphStorage {
  private roots = new Set<ForwardOp>();
  private ops = new Map<GraphTypes.Op, ForwardOp>();

  getRoots(): Set<ForwardOp> {
    return this.roots;
  }

  getOp(op: GraphTypes.Op): ForwardOp | undefined {
    return this.ops.get(op);
  }

  setOp(op: ForwardOp) {
    this.ops.set(op.op, op);
  }

  size() {
    return this.ops.size;
  }
}
