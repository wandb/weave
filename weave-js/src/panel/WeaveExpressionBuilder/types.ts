import {EditingNode, NodeOrVoidNode, OpDef, VarNode} from '@wandb/weave/core';

export interface WeaveExpressionBuilderProps {
  expr?: EditingNode;
  setExpression?: (expr: NodeOrVoidNode) => void;
  propsSetFilterFunction?: (expr: NodeOrVoidNode) => void;
}

export interface FilterBuilderRowState {
  id: string;
  lhsExpr: EditingNode | null;
  opDef: OpDef | null;
  rhsExpr: EditingNode | null;
  pendingExpr: EditingNode | null;
}

export interface FilterBuilderState {
  filterRowsState: {[id: string]: FilterBuilderRowState};
  columnKeys: string[] | null;
  rowNode: VarNode | null;
  combinedPendingExpr: EditingNode | null;
}
