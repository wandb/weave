import {
  constFunction,
  isVoidNode,
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
    if (
      frame.runColors == null ||
      isVoidNode(frame.runColors)
      // This was added by this pr https://github.com/wandb/weave/pull/865/files
      // to fix a slow query, it also as a result broke run colors in charts
      // I am going to comment out to fix run colors but we should take another look at this later
      // || !isAssignableTo(
      //   inputNode.type,
      //   taggedValue(typedDict({run: 'run'}), 'any')
      // )
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
