import * as GraphTypes from '../../model/graph/types';

export interface ForwardOp {
  op: GraphTypes.Op;
  outputNode: ForwardNode;
}

interface ForwardNode {
  node: GraphTypes.OutputNode;

  inputTo: Set<ForwardOp>;

  // Must not contain consumers which this op is consumed by!
  descendantTagConsumersWithAncestorProvider: {
    [opName: string]: Set<ForwardOp>;
  };
  consumedAsTagBy: Set<ForwardOp>;
  consumesTagFrom: Set<ForwardOp>;

  lambdaFnNodes?: GraphTypes.OutputNode[];

  // Legacy field -- stop using this!
  // Kept only so forwardOpInputs has sync access to results
  result?: any;
}

export interface ForwardGraphStorage {
  getRoots(): Set<ForwardOp>;
  getOp(op: GraphTypes.Op): ForwardOp | undefined;
  setOp(op: ForwardOp): void;
  size(): number;
}

export interface ForwardGraph extends ForwardGraphStorage {
  update(node: GraphTypes.Node): void;
  size(): number;
}
