import {
  constFunction,
  isAssignableTo,
  isVoidNode,
  Node,
  NodeOrVoidNode,
  opGetRunTag,
  opMapEach,
  opPick,
  opRunId,
  taggedValue,
  typedDict,
  voidNode,
  withNamedTag,
} from '@wandb/weave/core';
import {useMemo} from 'react';

import {usePanelContext} from '.././PanelContext';

export const useColorNode = (inputNode: Node): NodeOrVoidNode => {
  const {frame} = usePanelContext();
  return useMemo(() => {
    if (
      frame.runColors == null ||
      isVoidNode(frame.runColors) ||
      !isAssignableTo(
        inputNode.type,
        taggedValue(typedDict({run: 'run'}), 'any')
      )
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
