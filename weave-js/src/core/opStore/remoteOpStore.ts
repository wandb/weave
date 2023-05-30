import fetch from 'isomorphic-unfetch';
import {omit} from 'lodash';

import {callOpVeryUnsafe} from '../callers';
import {
  InputTypes,
  isAssignableTo,
  nullableOneOrMany,
  OpRenderInfo,
  outputTypeIsFunctionNode,
  Type,
} from '../model';
import {isSimpleTypeShape} from '../model';
import {makeStandardOpReturnType} from '../ops/opKinds';
import {opDefIsLowLevel} from '../runtimeHelpers';
import {BaseOpStore} from './static';

export interface ServerOpDef {
  name: string;
  input_types: InputTypes;
  // Not a node since we ignore ops with function output types on the python
  // side right now.
  // output_type: Type | OutputTypeAsNode<InputTypes>;
  output_type: Type;
  render_info?: OpRenderInfo;
  hidden?: boolean;
  mappable?: boolean;
  refine_output_type_op_name?: string;
}

interface WeaveServerOpList {
  data: ServerOpDef[];
}

const serverOpIsPanel = (op: ServerOpDef) => {
  if (outputTypeIsFunctionNode(op.output_type)) {
    return false;
  }
  return isAssignableTo(op.output_type, {type: 'Panel'});
};

const serverOpReturnsType = (op: ServerOpDef) => {
  if (outputTypeIsFunctionNode(op.output_type)) {
    return false;
  }
  return isSimpleTypeShape(op.output_type) && op.output_type === 'type';
};

// Primarily exported for testing reasons
export const buildOpStoreFromOpList = (opList: WeaveServerOpList) => {
  const remoteOpStore = new BaseOpStore();
  const userPanelOps: ServerOpDef[] = [];
  const refineOutputTypeOps: {[baseOpName: string]: string} = {};
  for (const op of opList.data) {
    const argDescriptions: {[key: string]: string} = {};
    for (const arg of Object.keys(op.input_types)) {
      argDescriptions[arg] = 'none'; // TODO(DG): Replace this with an actual description of args
    }

    let isPanel = false;
    if (serverOpIsPanel(op) || op.name.endsWith('_initialize')) {
      isPanel = true;
      userPanelOps.push(op);
    }

    if (op.refine_output_type_op_name != null) {
      refineOutputTypeOps[op.name] = op.refine_output_type_op_name;
    }

    let returnType;
    let argTypes;
    const arg0Name = Object.keys(op.input_types)[0];
    if (!op.mappable) {
      argTypes = op.input_types;
      returnType = op.output_type;
    } else {
      // Make the op types mappable. Weave Python implements the unmapped
      // and mapped ops as two different ops, where as in JS we typically
      // have a single op that accepts both types.
      // We do not handle constructing a mapped refiner here, as mapped
      // python ops will have a mapped refiner already, so the original
      // one will work. (I have not tested this with ops that have refiners
      // though so there could be an issue).
      argTypes = {
        [arg0Name]: nullableOneOrMany(op.input_types[arg0Name]),
        ...omit(op.input_types, [arg0Name]),
      } as {[key: string]: Type};
      returnType = makeStandardOpReturnType(() => op.output_type);
    }

    remoteOpStore.makeOp({
      name: op.name,
      hidden: op.hidden || isPanel || serverOpReturnsType(op),
      argTypes,
      returnType,
      description: op.name, // TODO(DG): replace with real description
      argDescriptions,
      returnValueDescription: op.name, // TODO(DG): replace with real description
      renderInfo: op.render_info,
      supportedEngines: new Set(['py']),
    });
  }
  // Pass 2: ensure all refine ops are assigned to their host op.
  for (const baseOpName in refineOutputTypeOps) {
    if (refineOutputTypeOps[baseOpName] != null) {
      const refineOpName = refineOutputTypeOps[baseOpName];
      const baseOp = remoteOpStore.getOpDef(baseOpName);
      if (baseOp != null && opDefIsLowLevel(baseOp)) {
        baseOp.refineNode = async (node, executableNode, client) => {
          const typeNode = callOpVeryUnsafe(
            refineOpName,
            executableNode.fromOp.inputs
          );
          const newType: Type = await client.query(typeNode as any);
          return {
            ...node,
            type: newType,
          };
        };
      }
    }
  }

  return {remoteOpStore, userPanelOps};
};

export const loadRemoteOpStore = (
  url: string
): Promise<{remoteOpStore: BaseOpStore; userPanelOps: ServerOpDef[]}> => {
  return fetch(url) // eslint-disable-line wandb/no-unprefixed-urls
    .then((res: any) => res.json())
    .then(buildOpStoreFromOpList)
    .catch((err: any) => {
      console.warn('Failed to load Ops from Remote Weave Server: ', err);
      const remoteOpStore = new BaseOpStore();
      const userPanelOps: ServerOpDef[] = [];
      return {remoteOpStore, userPanelOps};
    });
};
