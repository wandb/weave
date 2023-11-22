import {toWeaveType} from '@wandb/weave/components/Panel2/toWeaveType';
import {
  callOpVeryUnsafe,
  ConstNode,
  constNodeUnsafe,
  constString,
  isAssignableTo,
  Node,
  Op,
  opGet,
  OutputNode,
  Type,
  Weave,
} from '@wandb/weave/core';

const weaveConst = (val: any): ConstNode => {
  return constNodeUnsafe(toWeaveType(val), val);
};

type WeaveObjectTypeSpec = string | {name: string; base: WeaveObjectTypeSpec};

const weaveObjectTypeSpecToType = (typeSpec: WeaveObjectTypeSpec): Type => {
  let baseType: Type = {type: 'Object'};
  if (typeof typeSpec !== 'string') {
    baseType = weaveObjectTypeSpecToType(typeSpec.base);
  }
  const name = typeof typeSpec === 'string' ? typeSpec : typeSpec.name;
  return {
    type: name,
    _base_type: baseType,
  } as Type;
};

// Returns a value, not a ConstNode. You can still call weaveConst on it to
// get a node.
export const weaveObject = (
  typeName: WeaveObjectTypeSpec,
  attrs: {[key: string]: any}
) => {
  const objectType = weaveObjectTypeSpecToType(typeName);
  for (const [key, val] of Object.entries(attrs)) {
    (objectType as any)[key] = toWeaveType(val);
  }
  return {
    _type: objectType,
    ...attrs,
  };
};

class EasyNode implements OutputNode {
  type: Type;
  nodeType: 'output';
  fromOp: Op;

  constructor(node: OutputNode) {
    this.type = node.type;
    this.nodeType = node.nodeType;
    this.fromOp = node.fromOp;
  }

  getAttr(attrName: string) {
    return new EasyNode(
      callOpVeryUnsafe('Object-__getattr__', {
        obj: this as Node,
        name: constString(attrName),
      }) as OutputNode
    );
  }

  pick(key: string) {
    return new EasyNode(
      callOpVeryUnsafe('pick', {
        obj: this as Node,
        key: constString(key),
      }) as OutputNode
    );
  }
}

export const nodeToEasyNode = (node: OutputNode) => {
  return new EasyNode(node);
};

export const weaveGet = (uri: string, defaultVal?: any) => {
  if (defaultVal === undefined) {
    return new EasyNode(opGet({uri: constString(uri)}));
  }
  return new EasyNode(
    callOpVeryUnsafe('withdefault-get', {
      uri: constString(uri),
      default: constNodeUnsafe(toWeaveType(defaultVal), defaultVal),
    }) as OutputNode
  );
};

// const easyOpGetAttr = (self: Node, attrName: string) => {
//   return new EasyNode(
//     callOpVeryUnsafe('Object-__getattr__', {
//       uri: self,
//       default: constString(attrName),
//     }) as Node
//   );
// };

const mutate = async (
  weave: Weave,
  mutateOpName: string,
  objNode: Node,
  args: any[]
) => {
  const op = weave.op(mutateOpName);
  const inputTypesArray = Object.entries(op.inputTypes);
  if (args.length + 1 !== inputTypesArray.length) {
    throw new Error(
      `Expected ${inputTypesArray.length - 1} args, got ${args.length}`
    );
  }
  const opArgs: {[key: string]: Node} = {};

  for (let i = 0; i < inputTypesArray.length; i++) {
    const [k, paramType] = inputTypesArray[i];
    if (i === 0) {
      opArgs[k] = objNode;
    } else {
      const arg = args[i - 1];
      const argType = toWeaveType(arg);
      if (!isAssignableTo(argType, paramType)) {
        throw new Error(
          `Expected arg ${i} to be assignable to ${k}, got ${argType}`
        );
      }
      opArgs[k] = constNodeUnsafe(argType, arg);
    }
  }

  const calledMutation = callOpVeryUnsafe(mutateOpName, opArgs) as Node;

  return weave.client.action(calledMutation);
};

// Returns a local-artifact uri with the newly modified object
export const mutationSet = (
  weave: Weave,
  objNode: Node,
  val: any
): Promise<string> => {
  return mutate(weave, 'op-set', objNode, [weaveConst(val), {}]);
};

// Returns a local-artifact uri with the newly modified object
export const mutationAppend = (
  weave: Weave,
  objNode: Node,
  row: {[key: string]: any}
): Promise<string> => {
  return mutate(weave, 'op-append', objNode, [weaveConst(row), {}]);
};

export const mutationStreamTableLog = (
  weave: Weave,
  streamTableNode: Node,
  row: {[key: string]: any}
): Promise<string> => {
  return mutate(weave, 'stream_table-log', streamTableNode, [weaveConst(row)]);
};

export const mutationPublishArtifact = (
  weave: Weave,
  objNode: Node,
  entityName: string,
  projectName: string,
  artifactName: string
): Promise<string> => {
  return mutate(weave, 'op-publish_artifact', objNode, [
    weaveConst(artifactName),
    weaveConst(projectName),
    weaveConst(entityName),
  ]);
};
