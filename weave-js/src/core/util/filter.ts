import {EditingNode} from '../model/graph/editing/types';

export function filterNodes(
  node: EditingNode,
  filterFn: (inNode: EditingNode) => boolean,
  excludeFnBodies?: boolean
): EditingNode[] {
  let result: EditingNode[] = filterFn(node) ? [node] : [];
  if (
    node.nodeType === 'const' &&
    typeof node.type === 'object' &&
    node.type?.type === 'function' &&
    !excludeFnBodies
  ) {
    result = [...result, ...filterNodes(node.val, filterFn)];
  } else if (node.nodeType === 'output') {
    const childNodes = Object.values(node.fromOp.inputs).flatMap(inNode =>
      filterNodes(inNode, filterFn)
    );
    result = result.concat(childNodes);
  }
  return result;
}
