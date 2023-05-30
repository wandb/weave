import _ from 'lodash';

import * as Editing from './types';

export function nodesEqual(
  node1: Editing.EditingNode,
  node2: Editing.EditingNode
) {
  if (node1.nodeType === 'void' && node2.nodeType === 'void') {
    return true;
  }
  if (!_.isEqual(node1.type, node2.type)) {
    return false;
  }
  if (node1.nodeType === 'const' && node2.nodeType === 'const') {
    // Equal if shallow equal for now
    return node1.val === node2.val;
  } else if (node1.nodeType === 'var' && node2.nodeType === 'var') {
    return node1.varName === node2.varName;
  } else if (node1.nodeType === 'output' && node2.nodeType === 'output') {
    const op1 = node1.fromOp;
    const op2 = node2.fromOp;
    if (op1.name !== op2.name) {
      return false;
    }
    for (const key of Array.from(
      new Set(Object.keys(op1.inputs).concat(Object.keys(op2.inputs)))
    )) {
      if (op1.inputs[key] !== op2.inputs[key]) {
        return false;
      }
    }
    return true;
  }
  return false;
}
