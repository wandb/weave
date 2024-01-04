import * as _ from 'lodash';

import {pushFrame, resolveVar, varNode, voidNode} from './model';
import type {
  EditingNode,
  EditingOpInputs,
  EditingOutputNode,
} from './model/graph/editing';
import {nodesEqual} from './model/graph/editing/helpers';
import type {
  ConstNode,
  Definition,
  Node,
  NodeOrVoidNode,
  Stack,
} from './model/graph/types';
import {isFunction, isFunctionType} from './model/helpers';
import type {FunctionType, Type} from './model/types';

// Given a set of arguments, which are represented as nodes,
// and a function, which is a node that terminates at variables or
// constants, construct a new node that represents the function call
// TODO: callFunction should be updated to take a defineFunction result
// as its argument, and do call by position instead of argument name.
// This will allow users to name their function variables whatever they
// want, instead of what the caller expects.
// At the same time we should fix up

export default function callFunction(
  functionNode: NodeOrVoidNode,
  inputs: {[argName: string]: Node | EditingNode}
): Node {
  const {node} = dereferenceVariablesFromFrame(functionNode, inputs);
  // Don't do this check, we sometimes callFunction with a root function and
  // nothing in the frame
  // if (usedVarNames.length === 0) {
  //   throw new Error(
  //     'No function inputs used in call, this is probably a programming error'
  //   );
  // }
  return node;
}

// Dereference variables including walking const functions.
// TODO: should this also update the types when we replace variables?
function dereferenceVariablesFromFrame(
  functionNode: EditingNode,
  variables: {[argName: string]: EditingNode}
): {node: Node; usedVarNames: string[]} {
  const usedVarNames = new Set<string>();
  // walk function node, finding ops that have var inputs
  const node = mapNodes(
    functionNode,
    n => {
      if (n.nodeType === 'var') {
        const swapNode = variables[n.varName];
        if (swapNode == null) {
          return n;
        }
        usedVarNames.add(n.varName);
        return swapNode;
      } else if (n.nodeType === 'const' && isFunction(n.type)) {
        const fnInputTypes = n.type.inputTypes;
        const innerVariables = {...variables};
        if (fnInputTypes != null) {
          // If the function has declared input types, don't dereference those
          // variables, they will be provided at the time the function is called!
          for (const paramName of Object.keys(fnInputTypes)) {
            delete innerVariables[paramName];
          }
        }
        const {node: dereffedFn, usedVarNames: fnUsedVars} =
          dereferenceVariablesFromFrame(n.val, innerVariables);
        for (const usedVar of fnUsedVars) {
          usedVarNames.add(usedVar);
        }
        // If they're the same, return the same exact object! We
        // rely on memory equality in lots of places to make things
        // fast
        if (n.val === dereffedFn) {
          return n;
        }
        return {
          ...n,
          val: dereffedFn,
        };
      }
      return n;
    },
    true
  ) as Node; // can cast since we're feeding Nodes in

  // If we used a variable, do another pass. The new expression may
  // refer to other variables.
  //
  // it's possible that variables reference *themselves*, which
  // would cause infinite recursion -- we use !nodesEqual() to guard
  // against that
  // if (usedVarNames.size !== 0 && !nodesEqual(functionNode, node)) {
  //   const nextResult = dereferenceVariablesFromFrame(node, variables);
  //   return {
  //     node: nextResult.node,
  //     usedVarNames: Array.from(usedVarNames).concat(nextResult.usedVarNames),
  //   };
  // }
  return {node, usedVarNames: Array.from(usedVarNames)};
}

const VAR_NODE_NAME = '__funcParam__';

export function dereferenceAllVars(
  node: EditingNode,
  stack: Stack,
  addNullVars: boolean | undefined = false
) {
  const usedStack: Stack = [];
  const result = mapNodes(
    node,
    n => {
      if (n.nodeType === 'var') {
        const resolved = resolveVar(stack, n.varName);
        if (addNullVars && resolved == null) {
          usedStack.splice(0, 0, {
            name: n.varName,
            value: voidNode(),
            dirty: true,
          } as Definition);
        }

        if (resolved == null) {
          return n;
        }
        const {closure} = resolved;
        if (closure.value == null) {
          throw new Error('HOW!!!!');
        }
        usedStack.splice(0, 0, resolved.entry);
        if (
          closure.value.nodeType === 'var' &&
          closure.value.varName === VAR_NODE_NAME
        ) {
          return n;
        }
        const {node: subNode, usedStack: subUsedStack} = dereferenceAllVars(
          closure.value,
          closure.stack
        );
        for (const s of subUsedStack) {
          usedStack.splice(0, 0, s);
        }
        return subNode;
      } else if (n.nodeType === 'const' && isFunction(n.type)) {
        // For lambdas, push variables into the environment so when we
        // encounter them in the body we just swap for the same variable.
        const subEnv = pushFrame(
          stack,
          _.mapValues(n.type.inputTypes, () =>
            varNode('invalid', VAR_NODE_NAME)
          )
        );
        const {node: dereffedBody, usedStack: bodyUsedStack} =
          dereferenceAllVars(n.val, subEnv);
        for (const s of bodyUsedStack) {
          usedStack.splice(0, 0, s);
        }
        return {
          ...n,
          val: dereffedBody,
        };
      }
      return n;
    },
    true
  ) as NodeOrVoidNode;
  return {node: result, usedStack};
}

export function getUnresolvedVarNodes(node: EditingNode) {
  const result = new Set<string>();

  mapNodes(
    node,
    n => {
      if (n.nodeType === 'var') {
        result.add(n.varName);
      }
      return n;
    },
    true
  );

  return Array.from(result.keys());
}

// post-order traversal

export function mapNodes(
  node: EditingNode,
  mapFn: (inNode: EditingNode) => EditingNode,
  excludeFnBodies?: boolean
): EditingNode {
  if (node.nodeType === 'output') {
    // TODO: remove this jank
    if (node.fromOp.name === 'internal-lambdaClosureArgBridge') {
      return node;
    }
    const newInputs = _.mapValues(node.fromOp.inputs, inNode => {
      const mappedNode = mapNodes(inNode, mapFn, excludeFnBodies);
      // if (mappedNode.nodeType === 'void') {
      //   throw new Error('encountered void node while mapping');
      // }
      return mappedNode;
    });
    // Only replace node if an input has changed.
    // This way you can implement a findAndReplaceNode with mapNodes.
    let replace = false;
    for (const argName of Object.keys(node.fromOp.inputs)) {
      if (newInputs[argName] !== node.fromOp.inputs[argName]) {
        replace = true;
      }
    }
    if (!replace) {
      return mapFn(node);
    } else {
      return mapFn({
        ...node,
        fromOp: {
          ...node.fromOp,
          inputs: newInputs as any,
        },
      });
    }
  } else if (isFunctionLiteral(node) && !excludeFnBodies) {
    const newBody = mapNodes(node.val, mapFn, excludeFnBodies);

    if (!nodesEqual(node.val, newBody)) {
      return mapFn({
        ...node,
        val: newBody,
      });
    }

    return mapFn(node);
  } else {
    return mapFn(node);
  }
}
// This produces the wrong output type!
// Use callOpValid instead

export function callOpVeryUnsafe(
  opName: string,
  inputs: EditingOpInputs,
  outputType: Type = 'any'
): EditingOutputNode {
  return {
    nodeType: 'output',
    type: outputType,
    fromOp: {
      name: opName,
      inputs,
    },
  };
}

export function isFunctionLiteral(
  maybeFunction: EditingNode
): maybeFunction is ConstNode<FunctionType> {
  return (
    maybeFunction.nodeType === 'const' && isFunctionType(maybeFunction.type)
  );
}
