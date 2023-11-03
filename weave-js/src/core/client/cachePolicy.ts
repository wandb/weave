import * as GraphTypes from '../model/graph/types';
import {isConstNode, isOutputNode} from '../model';

const nodeIsImpureGetOp = (node: GraphTypes.Node<any>): boolean => {
  if (isOutputNode(node)) {
    if (node.fromOp.name === 'get') {
      const uriNode = node.fromOp.inputs.uri;
      if (isConstNode(uriNode)) {
        const uriVal = uriNode.val;
        if (typeof uriVal === 'string') {
          if (uriVal.includes(':latest')) {
            return true;
          }
        }
      }
    }
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

const graphIsPure = (node: GraphTypes.Node<any>): boolean => {
  if (isOutputNode(node)) {
    if (!nodeIsPure(node)) {
      return false;
    }
    for (const input of Object.values(node.fromOp.inputs)) {
      if (!graphIsPure(input)) {
        return false;
      }
    }
  }

  return true;
};

export const defaultCachePolicy = (node: GraphTypes.Node<any>): boolean => {
  if (!nodeIsPure(node)) {
    return false;
  }
  return true;
  // Once we have query time compilation of get ops, we can use a deeper check
  // return graphIsPure(node);
};
