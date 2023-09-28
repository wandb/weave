// High-level functions for manipulating and interpreting
// a compute graph.
//
// User code (UI) uses the functions in this file to manipulate and
// interact with the graph.

import {fromPairs, groupBy, mapValues, pickBy, range, zip} from 'lodash';

import callFunction, {
  dereferenceAllVars,
  isFunctionLiteral,
  mapNodes,
} from './callers';
import {Client} from './client';
import {
  EditingNode,
  EditingOp,
  EditingOpInputs,
  Frame,
  Node,
  NodeOrVoidNode,
  OpInputs,
  OutputNode,
  pushFrame,
  resolveVar,
  Stack,
  SupportedEnginesType,
  Type,
  VarNode,
} from './model';
import {constString, varNode} from './model/graph/construction';
import {nodesEqual} from './model/graph/editing';
import {isVarNode} from './model/graph/typeHelpers';
import {
  allObjPaths,
  isAssignableTo,
  isConstType,
  isFunction,
  isFunctionType,
  isListLike,
  isNullable,
  isTaggedValue,
  isTypedDictLike,
  listObjectType,
  maybe,
  nonNullable,
} from './model/helpers';
import {taggableStrip} from './model/modifiers';
import {determineOutputType} from './opStore/static';
import type {
  OpDef,
  OpDefGeneratedWeave,
  OpDefWeave,
  OpStore,
} from './opStore/types';
import {
  findConsumingOp,
  isBinaryOp,
  isBracketsOp,
  isDotChainedOp,
  isGetAttr,
  isUnaryOp,
  opDisplayName,
  opInputsAreValid,
  opSymbol,
} from './opStore/util';
import {opDefIsGeneratedWeave, opDefIsWeave} from './runtimeHelpers';
import {filterNodes} from './util/filter';

// Functions here assume that all ops have at least one input.
// Because functions must take at least one argument,
// otherwise, they're not a function, they're a constant. (Note:
// in normal programming languages, its perfectly acceptable to
// have zero-argument functions, but since we don't allow
// side-effects, they'd be useless here).

// For editing we use a graph definition that allows void nodes
// in op inputs

function opInputsAreNonVoid(opInputs: EditingOpInputs): opInputs is OpInputs {
  return !Object.values(opInputs).some(n => n.nodeType === 'void');
}

export function nodeIsExecutable(node: EditingNode): node is NodeOrVoidNode {
  const voidCount = filterNodes(node, n => n.nodeType === 'void').length;
  return voidCount === 0 || (voidCount === 1 && node.nodeType === 'void');
}

// function isChainedOp(op: CGTypes.EditingOp, opStore: OpStore) {
//   // of the form a.(x, y, z) or a.[x]
//   return isDotChainedOp(op, opStore) || isBracketsOp(op, opStore);
// }

export function isEditingNode(
  nodeOrOp: EditingNode | EditingOp
): nodeOrOp is EditingNode {
  return 'nodeType' in nodeOrOp;
}

export function isEditingOp(
  nodeOrOp: EditingNode | EditingOp
): nodeOrOp is EditingOp {
  return !isEditingNode(nodeOrOp);
}

async function mapNodesAsync(
  node: EditingNode,
  mapFn: (inNode: EditingNode) => Promise<EditingNode>,
  excludeFnBodies?: boolean
): Promise<EditingNode> {
  if (node.nodeType === 'output') {
    // TODO: remove this jank
    if (node.fromOp.name === 'internal-lambdaClosureArgBridge') {
      return Promise.resolve(node);
    }
    const newInputs = mapValues(node.fromOp.inputs, inNode => {
      const mappedNode = mapNodesAsync(inNode, mapFn, excludeFnBodies);
      // if (mappedNode.nodeType === 'void') {
      //   throw new Error('encountered void node while mapping');
      // }
      return mappedNode;
    });
    // Only replace node if an input has changed.
    // This way you can implement a findAndReplaceNode with mapNodesAsync.
    let replace = false;
    for (const argName of Object.keys(node.fromOp.inputs)) {
      if ((await newInputs[argName]) !== node.fromOp.inputs[argName]) {
        replace = true;
      }
    }
    if (!replace) {
      return mapFn(node);
    } else {
      const resolvedInputs = fromPairs(
        zip(Object.keys(newInputs), await Promise.all(Object.values(newInputs)))
      );
      return mapFn({
        ...node,
        fromOp: {
          ...node.fromOp,
          inputs: resolvedInputs as any,
        },
      });
    }
  } else if (isFunctionLiteral(node) && !excludeFnBodies) {
    const newBody = await mapNodesAsync(node.val, mapFn, excludeFnBodies);

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

export function expandAll(
  context: Client,
  node: EditingNode,
  stack: Stack
): Promise<EditingNode> {
  return mapNodesAsync(node, async checkNode => {
    if (checkNode.nodeType === 'output') {
      const opDef = context.opStore.getOpDef(checkNode.fromOp.name);
      if (opDefIsGeneratedWeave(opDef)) {
        const expandedNode = await expandGeneratedWeaveOp(
          context,
          opDef,
          checkNode as any,
          stack
        );
        const result = await expandAll(context, expandedNode as any, stack);
        return result;
      } else if (opDefIsWeave(opDef)) {
        const expandedNode = expandWeaveOp(opDef, checkNode as any);
        const result = await expandAll(context, expandedNode as any, stack);
        return result;
      }
    }
    return Promise.resolve(checkNode);
  });
}

export function findChainedAncestor(
  node: Node,
  findFn: (inNode: Node) => boolean,
  whileFn: (inNode: Node) => boolean
): Node | undefined {
  if (findFn(node)) {
    return node;
  }
  if (!whileFn(node)) {
    return undefined;
  }
  if (
    node.nodeType !== 'output' ||
    Object.keys(node.fromOp.inputs).length === 0
  ) {
    return undefined;
  }
  return findChainedAncestor(
    Object.values(node.fromOp.inputs)[0],
    findFn,
    whileFn
  );
}

export function findChainedAncestors(
  node: Node | undefined,
  findFn: (inNode: Node) => boolean
): Node[] {
  const results: Node[] = [];
  if (node == null) {
    return results;
  }
  if (findFn(node)) {
    results.push(node);
  }
  if (node.nodeType !== 'output') {
    return results;
  }
  return results.concat(
    findChainedAncestors(Object.values(node.fromOp.inputs)[0], findFn)
  );
}

// Returns free variables in expression, ie variables that aren't bound by a lambda.
// However, currently this is incorrect, since it doesn't walk lambdas at all!
// TODO: fix to walk lambdas, respecting lambda bound vars.
export function getFreeVars(node: NodeOrVoidNode): VarNode[] {
  if (node.nodeType === 'void') {
    return [];
  }
  return filterNodes(node, n => n.nodeType === 'var', true) as VarNode[];
}

// Throws an error if not found
export function replaceNode(
  node: EditingNode,
  toReplace: EditingNode,
  replaceWith: EditingNode
): EditingNode {
  const result = mapNodes(node, checkNode =>
    checkNode === toReplace ? replaceWith : checkNode
  );
  if (result === node) {
    // nothing changed!
    throw new Error('didnt find node to replace');
  }
  return result;
}

export function maybeReplaceNode(
  node: EditingNode,
  toReplace: EditingNode,
  replaceWith: EditingNode
): EditingNode {
  return mapNodes(node, checkNode =>
    checkNode === toReplace ? replaceWith : checkNode
  );
}

function expandWeaveOp(opDef: OpDefWeave, node: OutputNode) {
  return callFunction(opDef.body, node.fromOp.inputs as any);
}

export function expandGeneratedWeaveOp(
  context: Client,
  opDef: OpDefGeneratedWeave,
  node: OutputNode,
  stack: Stack
) {
  const macroStack = pushFrame(stack, node.fromOp.inputs);
  return opDef.expansion(
    node.fromOp.inputs,
    (innerNode: Node) =>
      refineEditingNode(context, innerNode, macroStack) as any,
    context
  );
}

// Note from Shawn: this function was in refineHelpers.ts, and dynamically imported
// in the middle of the hot refineEditingNode function. Doing so caused a long delay
// for some types of refines because each dynamic import seems to need to wait a few ms
// for some tick to occur.
// I moved it here, which means it can't directly rely on Op.*, so we just construct
// the op calls ourself with callOp
/**
 * Given a FunctionType, return a frame representing only the typed variables
 * that should be available inside the function. For the function body,
 * this should be merged with the frame of the parent context.
 *
 * opIndex would cause a circular import in hl.ts -- without it this could go there
 */
// TODO: name
export function getFunctionFrame(
  opName: string,
  firstArg: EditingNode,
  stack: Stack,
  opStore: OpStore
): Frame {
  // TODO: commented out below is what we _want_ to be able to do here. What holds us back
  // is that right now, all supported ops with function args take functions whose
  // type is dependent on the type of the first argument to the op. Easier by example:
  //
  // rows.filter((row) => row['name'] == 'Name')
  //
  // in this case, the function needs to take a row typed as a dictionary containing
  // a string property called 'name'. To do this, we need something like type parameters.
  // e.g. in TS filter would be typed:
  //
  // function filter<T>(arr: T[], callback: (item: T) => boolean) {}
  //
  // So the type of the second argument (callback) depends on the type of the first
  // (arr). We have no mechanism for doing this yet, so the code below doesn't work
  // unless you happen to be dealing with an op whose callback args ALWAYS take
  // the same argument types.

  // where functionType would be something pulled off of, e.g., opDef.inputTypes:

  // return mapValues(functionType.inputTypes, (inputType, argName) =>
  //   Graph.varNode(inputType, argName)
  // );

  // to get around this, we're implementing the type resolution behavior here for the
  // first few function-based op types we want to support. This is kind of like the
  // first pass on what would become `renderInfo`: eventually we will make this
  // behavior something we define on op definitions themselves. It's more dynamic
  // than render types, though, so it's gonna take some thought.

  // let frame: Code.Frame = {};
  let innerFrame: Frame = {};
  firstArg = dereferenceAllVars(firstArg as Node, stack).node;
  if (
    opName === 'groupby' ||
    opName === 'filter' ||
    opName === 'sort' ||
    opName === 'join' ||
    opName === 'map'
  ) {
    innerFrame = {
      row: callOpValid(
        'index',
        {
          arr: callOpValid('dropna', {arr: firstArg as any}, opStore),
          // This technically should be a var node called index of type number,
          // however, calls to refinedOutputType try to execute these frames
          // resulting in  executions.
          index: {nodeType: 'const', type: 'number', val: 0},
        },
        opStore
      ) as any,
    };
  } else if (opName === 'joinAll') {
    innerFrame = {
      row: callOpValid(
        'index',
        {
          arr: callOpValid(
            'index',
            {
              arr: callOpValid('dropna', {arr: firstArg as any}, opStore),
              // This technically should be a var node called index of type number,
              // however, calls to refinedOutputType try to execute these frames
              // resulting in  executions.
              index: {nodeType: 'const', type: 'number', val: 0},
            },
            opStore
          ) as any,
          index: {nodeType: 'const', type: 'number', val: 0},
        },
        opStore
      ) as any,
    };
  } else if (opName.startsWith('objectConstructor')) {
    innerFrame = {};
  } else {
    throw new Error('Invalid: function editor for unknown op: ' + opName);
  }
  return innerFrame;
}
// Preserves shallow-equality when it can, based on nodesEqual above.
// nodesEqual uses shallow equality to compare op inputs.
export async function refineEditingNode(
  client: Client,
  node: EditingNode,
  stack: Stack,
  cache?: Map<EditingNode, EditingNode>
): Promise<EditingNode> {
  if (cache?.has(node)) {
    return Promise.resolve(cache.get(node)!);
  }

  const cached = (result: EditingNode) => {
    cache?.set(node, result);
    cache?.set(result, result);
    return result;
  };

  if (node.nodeType === 'void') {
    return node;
  } else if (node.nodeType === 'var') {
    const resolved = resolveVar(stack, node.varName);
    if (resolved != null) {
      const resolvedNode = resolved.closure.value;
      let dereffedType = resolvedNode.type;
      if (
        resolvedNode.nodeType === 'const' &&
        !isConstType(resolvedNode.type)
      ) {
        // Convert to a const type here. determineOutputType converts this
        // back to a const Node before calling the op's outputType function,
        // which treats const nodes, like const types in weavejs.
        dereffedType = {
          type: 'const' as const,
          valType: resolvedNode.type,
          val: resolvedNode.val,
        };
      }
      const newNode = {...node, type: dereffedType} as EditingNode;

      if (nodesEqual(node, newNode)) {
        return cached(node);
      }

      return cached(newNode);
    }
    return cached(node);
  } else if (node.nodeType === 'const') {
    return cached(node);
  } else if (node.nodeType === 'output') {
    const op = node.fromOp;

    // try/catch here to handle cases where the weave1 op is not registered
    // (because it has a callable return type. We just return the node in that case.
    // This is incorrect, but prevents crashing for now.
    // TODO: Fix.
    let opDef: OpDef;
    try {
      opDef = client.opStore.getOpDef(op.name);
    } catch {
      return node;
    }

    // Otherwise improve all of this ops inputs first.
    const argNames = Object.keys(op.inputs);
    const argValues = Object.values(op.inputs);
    const argValuesRefined = await Promise.all(
      argValues.map(async (n, i) => {
        if (isFunctionLiteral(n)) {
          const functionBodyFrame = getFunctionFrame(
            op.name,
            argValues[0],
            stack,
            client.opStore
          );

          const functionBodyStack = pushFrame(stack, functionBodyFrame);
          const refinedFunctionBody = await refineEditingNode(
            client,
            n.val,
            functionBodyStack,
            cache
          );

          const expectedFunctionType = Object.values(opDef.inputTypes)[i];

          let inputTypes = n.type.inputTypes;
          if (
            isFunctionType(expectedFunctionType) &&
            Object.values(n.type.inputTypes).length === 0
          ) {
            // older versions of CG allowed functions with no arguments and would
            // infer the expected arguments from the opDef -- if we encounter such
            // a function, let's convert it to the new style:
            inputTypes = expectedFunctionType.inputTypes;

            // the function frame has even more specific type information for these
            // arguments:
            for (const key of Object.keys(inputTypes)) {
              if (functionBodyFrame[key]) {
                inputTypes[key] = functionBodyFrame[key].type;
              }
            }
          }

          const refinedFunctionLiteral = {
            ...n,
            type: {
              ...n.type,
              inputTypes,
              outputType: refinedFunctionBody.type,
            },
            val: refinedFunctionBody,
          };

          if (nodesEqual(n, refinedFunctionLiteral)) {
            return cached(n);
          }

          return cached(refinedFunctionLiteral);
        }

        return cached(await refineEditingNode(client, n, stack, cache));
      })
    );
    const inputsRefined: EditingOpInputs = {};
    argNames.forEach((name: any, i) => {
      // If an arg name is number like, then when we
      // do inputsRefined[name], it gets converted to a number.
      // This is a hack to compensate for that.
      try {
        const maybeNumber = parseInt(name, 10);
        if (!isNaN(maybeNumber)) {
          name = maybeNumber;
        }
      } catch (e) {
        // do nothing
      }

      inputsRefined[name] = argValuesRefined[i];

      // TODO: BIG Weave Python hacks here.
      // const inputType = inputsRefined[name].type;
      // if (isFunctionType(inputType)) {
      //   if (!isFunctionType(opDef.inputTypes[name])) {
      //     // inputsRefined[name].type = inputType.outputType;
      //     inputsRefined[name] = {
      //       nodeType: 'output',
      //       type: inputType.outputType,
      //       fromOp: {
      //         name: 'execute',
      //         inputs: {node: inputsRefined[name]},
      //       },
      //     };
      //   }
      // }
    });

    const hasValidInput = opInputsAreValid(inputsRefined, opDef);

    // If any input is void, the type of this node is void, and it can't be
    // refined. Just return it.
    if (!hasValidInput || !opInputsAreNonVoid(inputsRefined)) {
      console.warn(
        'Refine got invalid input for',
        node.fromOp.name,
        'opDef input types:',
        opDef.inputTypes,
        'actual types:',
        inputsRefined
      );
      const newNode = {
        ...node,
        nodeType: 'output' as const,
        fromOp: {
          ...op,
          inputs: inputsRefined,
        },
        type: 'invalid' as const,
      };

      if (nodesEqual(node, newNode)) {
        return cached(node);
      }

      return cached(newNode);
    }

    const nodeWithRefinedInputs = {
      ...node,
      nodeType: 'output' as const,
      type: node.type,
      fromOp: {
        ...op,
        inputs: inputsRefined,
      },
    };
    if (opDefIsWeave(opDef)) {
      const expandedOutput = await refineEditingNode(
        client,
        expandWeaveOp(opDef, nodeWithRefinedInputs),
        stack,
        cache
      );
      return cached({...nodeWithRefinedInputs, type: expandedOutput.type});
    } else if (opDefIsGeneratedWeave(opDef)) {
      const expandedOutput = await refineEditingNode(
        client,
        // For now, this is not too bad, but if we have a lot of these in an
        // expression, it could get non-performant as it has to expand the tree
        // each time. Leaving the cheaper one below for now.
        await expandAll(client, nodeWithRefinedInputs, stack),
        // (await expandGeneratedWeaveOp(
        //   client,
        //   opDef,
        //   nodeWithRefinedInputs,
        //   frame
        // )) as any,
        stack,
        cache
      );
      return cached({...nodeWithRefinedInputs, type: expandedOutput.type});
    } else if (opDef.refineNode != null) {
      // Make an executable version of nodeWithRefinedInputs by dereffing any
      // variables.
      const dereffed = dereferenceAllVars(nodeWithRefinedInputs, stack);
      const dereffedNode = dereffed.node;
      if (dereffedNode.nodeType !== 'output') {
        throw new Error(
          'refineEditingNode: expected dereffedNode.nodeType to be output, found ' +
            dereffedNode.nodeType
        );
      }
      const dereffedOp = dereffedNode.fromOp;
      const dereffedOpInputs = dereffedOp.inputs;
      if (!opInputsAreNonVoid(dereffedOpInputs)) {
        // We already dealt with this above
        throw new Error(
          'refineEditingNode: expected dereffed node inputs to be non-void'
        );
      }
      const executableOp = {
        ...dereffedOp,
        inputs: dereffedOpInputs,
      };
      const executableNode = {
        ...node,
        nodeType: 'output' as const,
        fromOp: executableOp,
        type: 'none' as const,
      };

      const resolvedNode = await opDef.refineNode(
        nodeWithRefinedInputs,
        executableNode,
        client,
        stack
      );

      if (nodesEqual(node, resolvedNode)) {
        return cached(node);
      } else {
        return cached(resolvedNode);
      }
    } else {
      const newNode2 = {
        ...nodeWithRefinedInputs,
        type: determineOutputType(opDef, inputsRefined),
      };

      if (nodesEqual(node, newNode2)) {
        return cached(node);
      }

      return cached(newNode2);
    }
  } else {
    throw new Error('refineEditingNode: unexpected node type');
  }
}

/** You must catch errors from function, and rethrow them in the render
 * thread.
 */
export async function refineNode(
  client: Client,
  node: Node,
  stack: Stack
): Promise<Node> {
  if (node.nodeType !== 'output') {
    return node;
  }
  return (await refineEditingNode(client, node, stack)) as Node;
}

function isProducibleType(type: Type): boolean {
  if (isFunction(type)) {
    return isProducibleType(type.outputType);
  }
  const PRODUCIBLE_TYPES: Type[] = [
    'string',
    'number',
    'boolean',
    'none',
    maybe('string'),
    maybe('number'),
    maybe('boolean'),
  ];
  return PRODUCIBLE_TYPES.find(t => isAssignableTo(t, type)) != null;
}

/**
 * Returns the list of op definitions that could replace op toReplace.
 *
 * Matches based on the input and return types of the ops.
 */
export function validReplacementOps(toReplace: EditingOp, opStore: OpStore) {
  const getOpDefOutputType = (opDef: OpDef, inputs?: EditingOpInputs): Type => {
    if (!inputs || !opInputsAreNonVoid(inputs)) {
      // we have no inputs or incomplete inputs, so we can't compute
      // the concrete type and we'll have to use 'any' instead.
      return 'any';
    }
    return determineOutputType(opDef, inputs);
  };

  const orderedInputs = Object.values(toReplace.inputs);
  const orderedInputTypes = orderedInputs.map(input => input.type);
  const outputType = getOpDefOutputType(
    opStore.getOpDef(toReplace.name),
    toReplace.inputs
  );

  return Object.values(opStore.allOps()).filter(opDef => {
    if (opDef.hidden) {
      return false;
    }

    // validate that the inputs match
    const opDefOrderedInputTypes = Object.values(opDef.inputTypes);

    if (opDefOrderedInputTypes.length !== orderedInputTypes.length) {
      return false;
    }

    for (const [index, inputType] of orderedInputTypes.entries()) {
      const opDefInputType = opDefOrderedInputTypes[index];

      if (!isAssignableTo(inputType, opDefInputType)) {
        return false;
      }
    }

    // try to validate that the return types match:
    const opDefArgNames = Object.keys(opDef.inputTypes);
    const newTypedInputs: EditingOpInputs = {};
    opDefArgNames.forEach(
      (name, i) => (newTypedInputs[name] = orderedInputs[i])
    );

    const opDefOutputType = getOpDefOutputType(opDef, newTypedInputs);

    // TODO: take node context into account here -- if the op is being consumed
    // by a node that can take multiple types, this line will incorrectly limit
    // us to only types that exactly match the old op's type
    return isAssignableTo(outputType, opDefOutputType);
  });
}

function isValidRootOp(opDef: OpDef) {
  return opDef.name === 'range' || opDef.name === 'root-project';
  // const inputTypeValues = Object.values(opDef.inputTypes);
  // return (
  //   inputTypeValues.filter(someLiteralAssignable).length ===
  //   inputTypeValues.length
  // );
}

// This is faster than lodash (see https://www.measurethat.net/Benchmarks/Show/3690/0/lodash-vs-set-intersection)
const setIntersection = <T>(a: Set<T>, b: Set<T>): Set<T> => {
  return new Set([...a].filter(i => b.has(i)));
};

function availableOps(
  supportedEngines: SupportedEnginesType,
  opStore: OpStore
) {
  const res = Object.values(opStore.allOps()).filter(
    opDef =>
      !opDef.hidden &&
      setIntersection(supportedEngines, opDef.supportedEngines).size > 0
  );
  return res;
}

const defaultEngineSet: SupportedEnginesType = new Set(['ts', 'py']);

export function rootOps(opStore: OpStore) {
  return Object.values(availableOps(defaultEngineSet, opStore)).filter(
    isValidRootOp
  );
}

export const supportedEngineForNode = (node: Node, opStore: OpStore) => {
  let supportedEngines: SupportedEnginesType = defaultEngineSet;
  if (node.nodeType === 'output') {
    mapNodes(node, n => {
      if (n.nodeType === 'output') {
        supportedEngines = setIntersection(
          supportedEngines,
          opStore.getOpDef(n.fromOp.name).supportedEngines
        );
      }
      return n;
    });
  }
  return supportedEngines;
};

export function availableOpsForChain(node: Node, opStore: OpStore): OpDef[] {
  return Object.values(
    availableOps(supportedEngineForNode(node, opStore), opStore)
  ).filter(opDef => {
    if (isValidRootOp(opDef)) {
      return false;
    }
    const inputTypes = Object.values(opDef.inputTypes);
    const inputType0 = inputTypes[0];
    const remainingTypes = inputTypes.slice(1);
    return (
      inputType0 != null &&
      isAssignableTo(node.type, inputType0) &&
      remainingTypes.every(isProducibleType)
    );
  });
}

export function pickSuggestions(objType: Type): string[] {
  // Currently this returns all paths to leave, but its useful to
  // be able to fetch intermediate nodes as weTypes. TODO: fix
  objType = taggableStrip(objType);

  if (isNullable(objType)) {
    objType = nonNullable(objType);
  }
  if (isTaggedValue(objType)) {
    objType = objType.value;
  }
  if (isListLike(objType)) {
    objType = listObjectType(objType);
  }
  if (isTaggedValue(objType)) {
    objType = objType.value;
  }
  let keys: string[] = [];
  if (isTypedDictLike(objType)) {
    const allPaths = allObjPaths(objType).map(pt =>
      pt.path.map(s => s.replace(new RegExp('\\.', 'g'), '\\.'))
    );
    // If we have nested paths that share the same tail key, included *. paths
    // in suggestions
    const sameLengthAndTailGroups = groupBy(
      allPaths,
      path => `${path.length}-${path[path.length - 1]}`
    );
    keys = Object.values(sameLengthAndTailGroups)
      .flatMap(paths => {
        if (paths.length === 1) {
          return paths;
        }
        const path0 = paths[0];
        const starredPath = range(path0.length - 1)
          .map(i => '*')
          .concat([path0[path0.length - 1]]);
        return [starredPath].concat(paths);
      })
      .map(path => path.join('.'));
  }
  return keys;
}

export function callOpValid(
  opName: string,
  inputs: OpInputs,
  opStore: OpStore
): Node {
  const opDef = opStore.getOpDef(opName);
  return {
    nodeType: 'output',
    type: determineOutputType(opDef, inputs),
    fromOp: {
      name: opName,
      inputs,
    },
  };
}

export function someNodes(
  node: EditingNode,
  predicateFn: (inNode: EditingNode) => boolean,
  excludeFnBodies?: boolean
): boolean {
  if (predicateFn(node)) {
    return true;
  } else if (
    node.nodeType === 'const' &&
    typeof node.type === 'object' &&
    node.type?.type === 'function' &&
    !excludeFnBodies
  ) {
    return someNodes(node.val, predicateFn, excludeFnBodies);
  } else if (node.nodeType === 'output') {
    const childPredicateValues = Object.values(node.fromOp.inputs).flatMap(
      inNode => someNodes(inNode, predicateFn, excludeFnBodies)
    );
    return childPredicateValues.some(v => v);
  }
  return false;
}

export function expressionVariables(node: EditingNode): VarNode[] {
  return filterNodes(node, isVarNode, true) as VarNode[];
}

const VAR_NODE_NAME = '__funcParam__';
export function allVarsWillResolve(node: EditingNode, stack: Stack): boolean {
  switch (node.nodeType) {
    case 'var':
      const resolved = resolveVar(stack, node.varName);
      if (
        resolved?.closure.value.nodeType === 'var' &&
        resolved.closure.value.varName === VAR_NODE_NAME
      ) {
        // This was a function argument we pushed in the isFunction block below
        return true;
      }
      if (resolved == null) {
        return false;
      }
      return allVarsWillResolve(resolved.closure.value, resolved.closure.stack);
    case 'output':
      return Object.values(node.fromOp.inputs).every(input =>
        allVarsWillResolve(input, stack)
      );
    case 'const':
      if (isFunction(node.type)) {
        return allVarsWillResolve(
          node.val,
          pushFrame(
            stack,
            // true indicates variable is a function argument, and will be
            // populated at call-time
            mapValues(node.type.inputTypes, () => varNode('any', VAR_NODE_NAME))
          )
        );
      }
      return true;
    default:
      return true;
  }
}

// Given an expression, update its VarNode's types to match the types of the
// variables the types of the nodes they reference.
export function updateVarTypes(node: EditingNode, stack: Stack): EditingNode {
  switch (node.nodeType) {
    case 'var':
      const resolved = resolveVar(stack, node.varName);
      if (resolved == null) {
        return node;
      }
      return {...node, type: resolved.closure.value.type};
    case 'output':
      return {
        ...node,
        fromOp: {
          ...node.fromOp,
          inputs: mapValues(node.fromOp.inputs, input =>
            updateVarTypes(input, stack)
          ),
        },
      };
    case 'const':
      if (isFunction(node.type)) {
        return {
          ...node,
          val: updateVarTypes(
            node.val,
            pushFrame(
              stack,
              // true indicates variable is a function argument, and will be
              // populated at call-time
              mapValues(node.type.inputTypes, (inputType, inputName) =>
                varNode(inputType, inputName)
              )
            )
          ),
        };
      }
  }
  return node;
}

// Given an expression, update its variable names to match the new name
export function updateVarNames(
  node: EditingNode,
  stack: Stack,
  oldName: string,
  newName: string
): EditingNode {
  switch (node.nodeType) {
    case 'var':
      if (node.varName === oldName) {
        return {...node, varName: newName};
      }
      return node;
    case 'output':
      return {
        ...node,
        fromOp: {
          ...node.fromOp,
          inputs: mapValues(node.fromOp.inputs, input =>
            updateVarNames(input, stack, oldName, newName)
          ),
        },
      };
    case 'const':
      if (isFunction(node.type)) {
        return {
          ...node,
          val: updateVarNames(
            node.val,
            pushFrame(
              stack,
              // true indicates variable is a function argument, and will be
              // populated at call-time
              mapValues(node.type.inputTypes, (inputType, inputName) =>
                varNode(inputType, inputName)
              )
            ),
            oldName,
            newName
          ),
        };
      }
  }
  return node;
}

export function couldBeReplacedByType(
  node: EditingNode,
  graph: EditingNode,
  replacementType: Type,
  opStore: OpStore
) {
  const consumer = findConsumingOp(node, graph);

  return (
    consumer != null &&
    isAssignableTo(
      replacementType,
      opStore.getOpDef(consumer.outputNode.fromOp.name).inputTypes[
        consumer.argName
      ]
    )
  );
}

export const getPlaceholderArg = (
  opDef: OpDef,
  argName: string
): EditingNode | null => {
  const argType = opDef.inputTypes[argName];
  if (isAssignableTo('string', argType)) {
    return constString('');
  }

  return null;
};

// certain op styles receive their first
// input from the LHS of the expression, instead of as an input parameter
export function shouldSkipOpFirstInput(opDef: OpDef): boolean {
  return ['chain', 'brackets', 'binary'].includes(opDef.renderInfo.type);
}

export const simpleNodeString = (node: EditingNode, opStore: OpStore): string =>
  node.nodeType === 'var'
    ? node.varName
    : node.nodeType === 'output'
    ? simpleOpString(node.fromOp, opStore)
    : node.nodeType === 'const'
    ? node.type === 'number' || node.type === 'int' || node.type === 'float'
      ? node.val.toString()
      : node.type === 'string'
      ? node.val
      : isFunctionType(node.type)
      ? simpleNodeString(node.val, opStore)
      : '?'
    : '-';

function simpleArgsString(args: EditingOpInputs, opStore: OpStore): string {
  return (
    '(' +
    Object.values(args)
      .map(v => simpleNodeString(v, opStore))
      .join(', ') +
    ')'
  );
}

function simpleOpString(op: EditingOp, opStore: OpStore): string {
  const argNames = Object.keys(op.inputs);
  const argValues = Object.values(op.inputs);
  if (op.name.endsWith('bin')) {
    // Bin ops like timestamp-bin produce really ugly strings. Simplify by not showing the rhs
    // argument. This makes default plot legends that are binned by timestamp much nicer.
    return `${simpleNodeString(argValues[0], opStore)} bin`;
  }

  if (isUnaryOp(op, opStore)) {
    return `${opSymbol(op, opStore)}${simpleNodeString(argValues[0], opStore)}`;
  }

  if (isBinaryOp(op, opStore)) {
    return `${simpleNodeString(argValues[0], opStore)} ${opSymbol(
      op,
      opStore
    )} ${simpleNodeString(argValues[1], opStore)}`;
  }

  if (isGetAttr(op, opStore)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const key = argValues[1];
    if (obj.nodeType === 'var' && key.nodeType === 'const') {
      return key.val;
    }
    return `${simpleNodeString(obj, opStore)}.${simpleNodeString(
      key,
      opStore
    )}`;
  }

  if (isBracketsOp(op, opStore)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const key = argValues[1];
    if (obj.nodeType === 'var' && key.nodeType === 'const') {
      return key.val;
    }
    return `${simpleNodeString(obj, opStore)}[${simpleNodeString(
      key,
      opStore
    )}]`;
  }

  if (isDotChainedOp(op, opStore)) {
    // Note, we skip rendering left hand side (obj.) when it is a
    // variable. So x.count is just count
    const obj = argValues[0];
    const leftHandSide =
      obj.nodeType === 'var' ? '' : simpleNodeString(argValues[0], opStore);
    return `${leftHandSide}${opDisplayName(op, opStore)}${
      argNames.length > 1
        ? simpleArgsString(
            pickBy(op.inputs, (v, k) => k !== argNames[0]),
            opStore
          )
        : ''
    }`;
  }
  return `${opDisplayName(op, opStore)} ${simpleArgsString(
    op.inputs,
    opStore
  )} `;
}

// Return a list where each element is a node that is the first input to the next
// element. The last element is the node itself.
export function linearize(node: NodeOrVoidNode) {
  function _linearize(n: OutputNode): OutputNode[] {
    const firstArg = Object.values(n.fromOp.inputs)[0];
    if (firstArg == null) {
      return [n];
    }
    if (firstArg.nodeType !== 'output') {
      return [n];
    }
    return [..._linearize(firstArg), n];
  }

  if (node.nodeType !== 'output') {
    return undefined;
  }
  return _linearize(node);
}
