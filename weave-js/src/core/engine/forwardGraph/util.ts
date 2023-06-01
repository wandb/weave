import {mapValues} from 'lodash';

import type {ForwardGraph, ForwardOp} from './types';

export function forwardOpInputs(
  fg: ForwardGraph,
  fo: ForwardOp
): {[x: string]: any} {
  return mapValues(fo.op.inputs, inputNode => {
    if (inputNode.nodeType === 'output') {
      const inputForwardOp = fg.getOp(inputNode.fromOp)!;
      return inputForwardOp.outputNode.result;
    } else if (inputNode.nodeType === 'const') {
      return inputNode.val;
    } else if (inputNode.nodeType === 'var') {
      return undefined;
    }
  });
}
