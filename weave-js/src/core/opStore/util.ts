import type {
  EditingNode,
  EditingOp,
  EditingOpInputs,
  EditingOutputNode,
} from '../model/graph/editing/types';
import {isAssignableTo, isSimpleTypeShape} from '../model/helpers';
import type {Type} from '../model/types';
import {filterNodes} from '../util/filter';
import {splitOnce} from '../util/string';
import type {OpDef, OpStore} from './types';

export const getOpDefsByDisplayName = (
  displayName: string,
  opStore: OpStore
): OpDef[] => {
  return Object.values(opStore.allOps()).filter(
    opDef => opDisplayName({name: opDef.name}, opStore) === displayName
  );
};

export function opDisplayName(op: {name: string}, opStore: OpStore): string {
  if (isBinaryOp(op, opStore) || isUnaryOp(op, opStore)) {
    return opSymbol(op, opStore);
  }
  if (op.name.indexOf('-') !== -1) {
    return splitOnce(op.name, '-')[1] as string;
  }
  return op.name;
}

export function opSymbol(op: {name: string}, opStore: OpStore): string {
  const opDef = opStore.getOpDef(op.name);

  if ((opDef.renderInfo as any).repr == null) {
    throw new Error(`op ${op.name} does not have a symbolic representation`);
  }

  return (opDef.renderInfo as any).repr;
}

export function isUnaryOp(op: {name: string}, opStore: OpStore) {
  return opStore.getOpDef(op.name).renderInfo.type === 'unary';
}

export function isBinaryOp(op: {name: string}, opStore: OpStore) {
  return opStore.getOpDef(op.name).renderInfo.type === 'binary';
}

export function isDotChainedOp(op: EditingOp, opStore: OpStore) {
  return opStore.getOpDef(op.name).renderInfo.type === 'chain';
}

// function isFunctionOp(op: {name: string}, opStore: OpStore) {
//   return opStore.getOpDef(op.name).renderInfo.type === 'function';
// }

export function isBracketsOp(op: {name: string}, opStore: OpStore) {
  return opStore.getOpDef(op.name).renderInfo.type === 'brackets';
}

export function isGetAttr(op: {name: string}, opStore: OpStore) {
  return op.name === 'Object-__getattr__';
}

enum Side {
  LEFT,
  RIGHT,
}

function getOpAssociativity(opName: string) {
  if (opName === 'number-powBinary') {
    return Side.RIGHT;
  }

  return Side.LEFT;
}

// low to high
const opPrecedences = [
  ['or'],
  ['and'],
  ['number-equal', 'number-notEqual'],
  ['number-less', 'number-greater', 'number-lessEqual', 'number-greaterEqual'],
  ['number-add', 'number-sub'],
  ['number-mult', 'number-div', 'number-modulo'],
  ['number-negate', 'boolean-not'],
  ['number-powBinary'],
];

function getOpPrecedence(opName: string) {
  const index = opPrecedences.findIndex(opNames => opNames.includes(opName));

  // ops without a defined precedence are all assumed to have the highest
  // possible precedence
  const result = index === -1 ? opPrecedences.length : index;
  return result;
}

/**
 * Return true if the given op needs parentheses to clarify the order of
 * operations given its position in graph.
 */
export function opNeedsParens(
  op: EditingOp,
  graph: EditingNode,
  opStore: OpStore
) {
  if (!isBinaryOp(op, opStore)) {
    return false;
  }

  let outputOfOp: EditingOutputNode<Type> | undefined;

  try {
    outputOfOp = findOutputOf(op, graph);
  } catch (e) {
    // findOutputOf will fail if the op is not currently in the graph
    // (which can happen when logging an op we're about to insert)
    //
    // this is actually fine -- it just means we don't need parens
  }

  if (!outputOfOp) {
    return false;
  }

  const {outputNode: consumingOutputNode, argIndex} =
    findConsumingOp(outputOfOp, graph) || {};

  if (!consumingOutputNode) {
    return false;
  }

  if (
    isDotChainedOp(consumingOutputNode.fromOp, opStore) ||
    isBracketsOp(consumingOutputNode.fromOp, opStore)
  ) {
    // these are special cases

    if (argIndex === 0) {
      // if we are the first argument, we should always be parenthesized
      // (given that we're a binary op, which we've already asserted above)

      // e.g. (x + y).avg() or
      //      (x + 1)[1]
      return true;
    }

    // if we're another argument, we should never be parenthesized

    // e.g. x.func(y + z, a + b) or
    //      x[y + z]
    // in both cases, the addition operators don't need parentheses
    return false;
  }

  const ourPrecedence = getOpPrecedence(op.name);

  // which arg could potentially be associated with the
  // consuming op, instead of us?
  let possiblyAmbiguousArg: EditingNode;
  let possibleClaimingArgNameInConsumer: string;

  if (argIndex === 0) {
    // we're the lhs, so the parent would "take" our rhs
    // for its lhs instead
    // e.g., we are:
    // 3 + 4
    // in
    // (3 + 4) / 5
    // and we need to distinguish ourselves from
    // 3 + 4 / 5
    possiblyAmbiguousArg = op.inputs.rhs;
    possibleClaimingArgNameInConsumer = 'lhs';
  } else {
    // we're the rhs, so the parent would "take" our lhs
    // for its rhs instead
    // e.g., we are:
    // 3 + 4
    // in
    //  5 / (3 + 4)
    // and we need to distinguish ourselves from
    // 5 / 4 + 4
    possiblyAmbiguousArg = op.inputs.lhs;
    possibleClaimingArgNameInConsumer = 'rhs';
  }

  // an alternate parenthesization would "move" one of our args to the
  // consuming expression -- here we check if that move would satisfy
  // the consumer's type constraints for inputs.

  // if not, there's no need to parenthesize: the types make the order of
  // operations unambiguous
  const consumingOpDef = opStore.getOpDef(consumingOutputNode.fromOp.name);
  const consumerCouldStealArg = nodeIsValidAsNamedArg(
    consumingOpDef,
    possibleClaimingArgNameInConsumer,
    possiblyAmbiguousArg
  );

  // If consumer can't steal arg, we never need parens
  if (!consumerCouldStealArg) {
    return false;
  }

  // If it can, we need to compare our precedence vs consumers,
  // accounting for associativity
  const consumingOpPrecedence = getOpPrecedence(
    consumingOutputNode.fromOp.name
  );
  const consumingOpAssociativity = getOpAssociativity(
    consumingOutputNode.fromOp.name
  );
  const ourSide = argIndex !== 0 ? Side.RIGHT : Side.LEFT;

  if (consumingOpAssociativity === Side.LEFT) {
    // Consumer is left-associative, i.e., prefers (a op b) op c

    if (ourSide === Side.LEFT && consumingOpPrecedence > ourPrecedence) {
      // e.g., (a + b) / c
      return true;
    }

    if (ourSide === Side.RIGHT && consumingOpPrecedence >= ourPrecedence) {
      // e.g., a / (b + c)
      return true;
    }
  } else {
    // Consumer is right-associative, i.e., prefers a op (b op c)

    if (ourSide === Side.LEFT && consumingOpPrecedence >= ourPrecedence) {
      // e.g., (a ** b) ** c
      return true;
    }

    if (ourSide === Side.RIGHT && consumingOpPrecedence > ourPrecedence) {
      // e.g., a *** (b ** c)
      // "***" is an imaginary operator that is right-associative and higher precedence than **
      return true;
    }
  }

  return false;
}

export function findConsumingOp(
  node: EditingNode,
  graph: EditingNode
):
  | {
      argIndex: number;
      argName: string;
      outputNode: EditingOutputNode;
    }
  | undefined {
  const consumingOps = filterNodes(graph as any, checkNode => {
    if (checkNode.nodeType === 'output') {
      const innerArgNodes = Object.values(checkNode.fromOp.inputs);
      return innerArgNodes.find(n => n === node) != null;
    }
    return false;
  });
  if (consumingOps.length === 0) {
    return undefined;
  }
  if (consumingOps.length > 1) {
    throw new Error('too many consuming ops, this is not an expression');
  }
  const consumingOpNode = consumingOps[0];
  if (consumingOpNode.nodeType !== 'output') {
    // impossible, we just checked above.
    throw new Error('findConsumingOp: found non-output consumingOpNode');
  }
  const argNames = Object.keys(consumingOpNode.fromOp.inputs);
  const argNodes = Object.values(consumingOpNode.fromOp.inputs);
  const argIndex = argNodes.findIndex(n => n === node);
  return {argIndex, argName: argNames[argIndex], outputNode: consumingOpNode};
}

function findOutputOf(op: EditingOp, graph: EditingNode): EditingOutputNode {
  const outputNodes = filterNodes(
    graph,
    node => node.nodeType === 'output' && node.fromOp === op
  );

  if (outputNodes.length !== 1) {
    // not using opToString here because it would recursively call findOutputOf
    throw new Error(
      `Expected exactly one output node for op ${op.name} in ${JSON.stringify(
        graph
      )}, but found ${outputNodes.length}`
    );
  }

  return outputNodes[0] as EditingOutputNode;
}

function nodeIsValidAsNamedArg(
  opDef: OpDef,
  argName: string,
  possibleArgValue: EditingNode
) {
  const inputType = opDef.inputTypes[argName];

  // if inputType is null, allow all types! This is to handle the current
  // manyX ugliness in some ops (ops that take many args). But other bugs
  // may result :(
  return (
    inputType == null ||
    isAssignableTo(possibleArgValue.type, inputType) ||
    // Hack to make Promises (Run<X>) work. It acts like its assignable to X
    // But we don't want the panel autosuggest to trigger.
    // TODO: fix this situation.
    (!isSimpleTypeShape(possibleArgValue.type) &&
      possibleArgValue.type.type === 'run-type' &&
      isAssignableTo(possibleArgValue.type._output, inputType))
  );
}

export function opInputsAreValid(inputs: EditingOpInputs, opDef: OpDef) {
  let hasValidInput = true;
  for (const [argName, argValue] of Object.entries(inputs)) {
    if (!nodeIsValidAsNamedArg(opDef, argName, argValue)) {
      hasValidInput = false;
    }
  }
  return hasValidInput;
}
