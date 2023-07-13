import {findChainedAncestor, linearize, replaceNode} from './hl';
import {ConstNode, NodeOrVoidNode, Op, OutputNode, VarNode} from './model';
import {StaticOpStore} from './opStore';
import {opDefIsLowLevel} from './runtimeHelpers';

export const CONSTRUCTOR_OP_NAMES = ['list', 'get', 'dict', 'timestamp'];

const CLIENT_MUTATE_OK_ACCESSOR_OP_NAMES = [
  'pick',
  'Object-__getattr__',
  'index',
];

export const callResolverSimple = (
  opName: string,
  inputs: {[key: string]: any},
  fromOp: Op
): any => {
  const tsOps = StaticOpStore.getInstance();
  const opDef = tsOps.getOpDef(opName);
  if (!opDefIsLowLevel(opDef)) {
    throw new Error('opDef is not low level ' + opDef.name);
  }
  const res = opDef.resolver(
    inputs,
    null as any,
    // Passing this in because opKinds uses it. null is invalid for the type.
    // But we don't expect it to be used.
    {op: fromOp, outputNode: null as any},
    null as any,
    null as any
  );
  if (res && typeof res.then === 'function') {
    // The resolver returned a promise, its async!
    // Client resolution shouldn't be used for expensive async stuff.
    // If this happens, you may need to set resolverIsSync on the op.
    throw new Error('resolver returned a promise for op ' + opName);
  }
  return res;
};

interface SetResultOK {
  ok: true;
  value: any;
}

interface SetResultInvalid {
  ok: false;
}

type SetResult = SetResultOK | SetResultInvalid;

// We look for a sequenc like constructor, constructor, accessor, accessor, accessor, ...
// More complicated sequences by may be possible to handle but are not
// currently supported.
const constructorSplit = (linearNodes: OutputNode[] | undefined) => {
  linearNodes = linearNodes ?? [];
  const constructorNodes: OutputNode[] = [];
  const accessorNodes: OutputNode[] = [];
  let constructorSeq = true;
  for (const node of linearNodes) {
    const isClientSafeAccessor = CLIENT_MUTATE_OK_ACCESSOR_OP_NAMES.includes(
      node.fromOp.name
    );
    if (constructorSeq && isConstructor(node)) {
      constructorNodes.push(node);
    } else if (constructorSeq && isClientSafeAccessor) {
      constructorSeq = false;
      accessorNodes.push(node);
    } else if (
      !constructorSeq &&
      CLIENT_MUTATE_OK_ACCESSOR_OP_NAMES.includes(node.fromOp.name)
    ) {
      accessorNodes.push(node);
    } else {
      return null;
    }
  }
  return {constructorNodes, accessorNodes};
};

// Perform a client side set mutation, returning the new value.
// Should be equivalent to the server side set mutation (but handles fewer ops).
// const clientSet = (linearNodes: OutputNode[] | undefined, value: any) => {
export const clientSet = (target: NodeOrVoidNode, value: any): SetResult => {
  const linearNodes = linearize(target);
  const splitResult = constructorSplit(linearNodes);
  if (splitResult == null) {
    return {ok: false};
  }

  const {accessorNodes} = splitResult;
  if (accessorNodes.length === 0) {
    return {ok: true, value};
  }
  let arg0 = Object.values(accessorNodes[0].fromOp.inputs)[0];
  const results: any[] = [];
  const opInputs: Array<{[key: string]: any}> = [];
  // Execute forward
  for (const node of accessorNodes) {
    const inputs = {...node.fromOp.inputs};
    inputs[Object.keys(inputs)[0]] = arg0;
    arg0 = callResolverSimple(node.fromOp.name, inputs, node.fromOp);
    opInputs.push(inputs);
    results.push(arg0);
  }

  let res = value;

  for (let i = accessorNodes.length - 1; i >= 0; i--) {
    const node = accessorNodes[i];
    const inputs = Object.values(opInputs[i]);
    if (node.fromOp.name === 'pick') {
      inputs[0][inputs[1].val] = res;
    } else if (node.fromOp.name === 'Object-__getattr__') {
      inputs[0][inputs[1].val] = res;
    } else if (node.fromOp.name === 'index') {
      inputs[0][inputs[1].val] = res;
    }
    res = inputs[0];
  }
  return res;
};

export function getChainRootVar(node: NodeOrVoidNode): VarNode | undefined {
  if (node.nodeType === 'void') {
    return undefined;
  }
  return findChainedAncestor(
    node,
    n => n.nodeType === 'var',
    n => !isConstructor(n)
  ) as VarNode | undefined;
}

export function isConstructor(node: NodeOrVoidNode) {
  return (
    node.nodeType === 'const' ||
    (node.nodeType === 'output' &&
      CONSTRUCTOR_OP_NAMES.includes(node.fromOp.name))
  );
}

export function getChainRootConstructor(
  node: NodeOrVoidNode
): ConstNode | OutputNode | undefined {
  if (node.nodeType === 'void') {
    return undefined;
  }
  return findChainedAncestor(
    node,
    n => isConstructor(n),
    n => !isConstructor(n)
  ) as ConstNode | undefined;
}

export function replaceChainRoot(
  node: NodeOrVoidNode,
  replaceWith: NodeOrVoidNode
): NodeOrVoidNode {
  if (node.nodeType === 'output') {
    const chainRoot = getChainRootConstructor(node);
    if (chainRoot == null) {
      // Shouldn't happen since we check if output node above.
      throw new Error('no chain root found');
    }
    return replaceNode(node, chainRoot, replaceWith) as NodeOrVoidNode;
  }
  return replaceWith;
}
