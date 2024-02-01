import {
  constFunction,
  isAssignableTo,
  isListLike,
  isVoidNode,
  list,
  listObjectType,
  Node,
  NodeOrVoidNode,
  opGetRunTag,
  opMapEach,
  opPick,
  opRunId,
  voidNode,
  withNamedTag,
} from '@wandb/weave/core';
import {useMemo} from 'react';

import {usePanelContext} from '.././PanelContext';

export const useColorNode = (inputNode: Node): NodeOrVoidNode => {
  const {frame} = usePanelContext();
  return useMemo(() => {
    let rowType = inputNode.type;
    let limit = 10;
    while (isListLike(rowType) && limit > 0) {
      rowType = listObjectType(rowType);
      limit--;
    }
    if (
      frame.runColors == null ||
      isVoidNode(frame.runColors) //  ||
      // !isAssignableTo(rowType, taggedValue(typedDict({run: 'run'}), 'any'))
    ) {
      return voidNode();
    }
    return opMapEach({
      obj: inputNode,
      mapFn: constFunction({row: withNamedTag('run', 'run', 'any')}, ({row}) =>
        opPick({
          obj: frame.runColors as Node, // Checked above
          key: opRunId({
            run: opGetRunTag({obj: row as any}),
          }),
        })
      ),
    });
  }, [frame, inputNode]);
};
