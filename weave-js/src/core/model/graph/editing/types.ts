import type {Type} from '../../types';
import type {BaseNode, ConstNode, VarNode, VoidNode} from '../types';

export interface EditingOutputNode<T extends Type = Type> extends BaseNode<T> {
  nodeType: 'output';
  fromOp: EditingOp;

  // Server-side only
  id?: string;
}

export type EditingNode<T extends Type = Type> = {
  // Hack: Keep the id of syntax node that produced me for building the ast<>cg map
  // New note: We don't need this anymore, but its saved in some graphs and we need
  // to strip it out in some locations in the code, so leaving in the type.
  __syntaxKeyRef?: number;
} & (EditingOutputNode<T> | ConstNode<T> | VarNode<T> | VoidNode);

export type EditingOpInputs = {[key: string]: EditingNode};

export interface EditingOp {
  name: string;
  inputs: EditingOpInputs;
}
