import {has} from '../../util/has';
import {isAssignableTo} from '../helpers';
import type {Type} from '../types';
import type {
  BaseNode,
  ConstNode,
  InputTypes,
  Node,
  NodeOrVoidNode,
  OutputNode,
  OutputTypeAsNode,
  OutputTypeGeneric,
  TypeFn,
  VarNode,
  VoidNode,
} from './types';

function isBaseNode(maybeNode: any): maybeNode is BaseNode<Type> {
  return has('type', maybeNode);
}

export function isConstNode(maybeNode: any): maybeNode is ConstNode {
  return (
    isBaseNode(maybeNode) &&
    has('nodeType', maybeNode) &&
    maybeNode.nodeType === 'const'
  );
}
export function isVarNode(maybeNode: any): maybeNode is VarNode {
  return (
    isBaseNode(maybeNode) &&
    has('nodeType', maybeNode) &&
    maybeNode.nodeType === 'var'
  );
}

export function isOutputNode(maybeNode: any): maybeNode is OutputNode {
  return (
    isBaseNode(maybeNode) &&
    has('nodeType', maybeNode) &&
    maybeNode.nodeType === 'output'
  );
}

export function isVoidNode(maybeNode: any): maybeNode is VoidNode {
  return (
    isBaseNode(maybeNode) &&
    has('nodeType', maybeNode) &&
    maybeNode.nodeType === 'void'
  );
}

export function isNonVoidNode(maybeNode: any): maybeNode is Node {
  return (
    isOutputNode(maybeNode) || isVarNode(maybeNode) || isConstNode(maybeNode)
  );
}

export function isNodeOrVoidNode(maybeNode: any): maybeNode is NodeOrVoidNode {
  return (
    isOutputNode(maybeNode) ||
    isVarNode(maybeNode) ||
    isConstNode(maybeNode) ||
    isVoidNode(maybeNode)
  );
}

export function isConstNodeWithType<T extends Type>(
  constNode: ConstNode<Type>,
  type: T
): constNode is ConstNode<T> {
  return isAssignableTo(constNode.type, type);
}

export function isConstNodeWithObjectType(
  maybeNode: any
): maybeNode is ConstNode<Type> {
  return (
    isConstNode(maybeNode) &&
    has('_is_object', maybeNode.type) &&
    maybeNode.type._is_object === true
  );
}

export const outputTypeIsType = (
  ot: OutputTypeGeneric<any, any>
): ot is Type => {
  return !outputTypeIsExecutable(ot) && !outputTypeIsFunctionNode(ot);
};

export const outputTypeIsExecutable = <IT extends InputTypes, RT extends Type>(
  ot: OutputTypeGeneric<IT, RT>
): ot is TypeFn<IT, RT> => {
  return typeof ot === 'function';
};

export const outputTypeIsFunctionNode = <IT extends InputTypes>(
  ot: OutputTypeGeneric<IT, any>
): ot is OutputTypeAsNode<IT> => {
  return (
    isConstNode(ot) &&
    typeof ot.type === 'object' &&
    ot.type.type === 'function'
  );
};
