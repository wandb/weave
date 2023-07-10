import * as _ from 'lodash';

import type {ConstType, FunctionTypeSpecific, Type} from '../types';
import type {
  ConstNode,
  InputTypes,
  Node,
  TypeToTSTypeInner,
  VarNode,
  VoidNode,
} from './types';

export function constType<VT extends Type>(
  val: TypeToTSTypeInner<VT>,
  valType: VT
): ConstType<VT> {
  return {
    type: 'const',
    valType,
    val,
  };
}

// Sometimes, Typescript cannot calculate the type of ConstNode.val correctly
// This is an escape hatch to allow value to bet set w/ loose typing, but this
// is unsafe because in most cases this can hide genuine type mistakes.
export function constNodeUnsafe<T extends Type>(type: T, value: any) {
  if (typeof value === 'undefined') {
    throw new Error(`Cannot create const node undefined value`);
  }

  return {
    nodeType: 'const' as const,
    type,
    val: value,
  };
}

export function constNode<T extends Type>(
  type: T,
  value: TypeToTSTypeInner<T>
): ConstNode<T> {
  if (typeof value === 'undefined') {
    throw new Error(`Cannot create const node undefined value`);
  }

  return {
    nodeType: 'const' as const,
    type,
    val: value,
  };
}

export function constString(s: string): ConstNode<'string'> {
  return constNodeUnsafe('string', s);
}
export function constNumber(n: number): ConstNode<'number'> {
  return constNodeUnsafe('number', n);
}
export function constTimestamp(n: number): ConstNode<{type: 'timestamp'}> {
  return constNodeUnsafe({type: 'timestamp'}, n);
}

export function constNumberList(
  ns: number[]
): ConstNode<{type: 'list'; objectType: 'number'}> {
  return constNodeUnsafe({type: 'list', objectType: 'number'}, ns);
}
export function constTimestampList(
  ns: number[]
): ConstNode<{type: 'list'; objectType: {type: 'timestamp'}}> {
  return constNodeUnsafe({type: 'list', objectType: {type: 'timestamp'}}, ns);
}

export function constStringList(
  ss: string[]
): ConstNode<{type: 'list'; objectType: 'string'}> {
  return constNodeUnsafe({type: 'list', objectType: 'string'}, ss);
}
export function constBoolean(b: boolean): ConstNode<'boolean'> {
  return constNodeUnsafe('boolean', b);
}
export function constFunction<IT extends InputTypes, RT extends Type>(
  parameters: InputTypes,
  fnBody: (inputs: {
    [K in keyof IT]: VarNode<IT[K]>;
  }) => Node<RT>
): ConstNode<FunctionTypeSpecific<InputTypes, RT>> {
  const varNodes = _.mapValues(parameters, (paramType, varName) =>
    varNode(paramType, varName)
  ) as {[K in keyof IT]: VarNode<IT[K]>};

  const fnNode = fnBody(varNodes);
  return constNodeUnsafe(
    {type: 'function', inputTypes: parameters, outputType: fnNode.type},
    fnNode
  );
}
export function constLink(name: string, url: string): ConstNode<'link'> {
  return constNodeUnsafe('link', {name, url});
}
export function constDate(date: Date): ConstNode<'date'> {
  return constNodeUnsafe('date', date);
}
export function constNone(): ConstNode<'none'> {
  return constNodeUnsafe('none', null);
}
export function varNode<T extends Type>(type: T, varName: string): VarNode<T> {
  return {
    nodeType: 'var',
    type,
    varName,
  };
}

export function voidNode(): VoidNode {
  return {nodeType: 'void', type: 'invalid'};
}
