import {isConstNode, isOutputNode} from '../model';
import * as GraphTypes from '../model/graph/types';

const isGetNode = (
  node: GraphTypes.Node<any>
): node is GraphTypes.OutputNode<any> => {
  if (isOutputNode(node)) {
    if (node.fromOp.name === 'get') {
      return true;
    }
  }
  return false;
};

const getStringValFromNode = (
  node: GraphTypes.Node<any>
): string | undefined => {
  if (isConstNode(node)) {
    const uriVal = node.val;
    if (typeof uriVal === 'string') {
      return uriVal;
    }
  }
  return undefined;
};

const WANDB_COMMIT_HASH_LENGTH = 20;

const isHexString = (s: string): boolean => {
  return /^[0-9a-f]+$/i.test(s);
};

const isLikelyCommitHash = (version: string): boolean => {
  // This is the heuristic we use everywhere to tell if a version is an alias or not
  return isHexString(version) && version.length === WANDB_COMMIT_HASH_LENGTH;
};

const getAliasFromUri = (uri: string): string => {
  const uriParts = uri.split(':');
  const aliasPart = uriParts[uriParts.length - 1];
  const alias = aliasPart.split('/')[0];
  return alias;
};

const nodeIsImpureGetOp = (node: GraphTypes.Node<any>): boolean => {
  if (isGetNode(node)) {
    const uriVal = getStringValFromNode(node.fromOp.inputs.uri);
    if (uriVal && isLikelyCommitHash(getAliasFromUri(uriVal))) {
      return false;
    }
    return true;
  }
  return false;
};

const nodeIsPure = (node: GraphTypes.Node<any>): boolean => {
  if (nodeIsImpureGetOp(node)) {
    return false;
  }
  // Other checks here
  return true;
};

// const graphIsPure = (node: GraphTypes.Node<any>): boolean => {
//   if (isOutputNode(node)) {
//     if (!nodeIsPure(node)) {
//       return false;
//     }
//     for (const input of Object.values(node.fromOp.inputs)) {
//       if (!graphIsPure(input)) {
//         return false;
//       }
//     }
//   }

//   return true;
// };

export const defaultCachePolicy = (node: GraphTypes.Node<any>): boolean => {
  if (!nodeIsPure(node)) {
    return false;
  }
  return true;
  // Once we have query time compilation of get ops, we can use a deeper check
  // return graphIsPure(node);
};
