import * as Types from '@wandb/cg/browser/model/types';
import * as CG from '@wandb/cg/browser/graph';
import {usePanelContext} from '.././PanelContext';
import * as Op from '@wandb/cg/browser/ops';
import {useMemo} from 'react';

export const useColorNode = (inputNode: Types.Node): Types.NodeOrVoidNode => {
  const {frame} = usePanelContext();
  return useMemo(() => {
    if (frame.runColors == null) {
      return CG.voidNode();
    }
    return Op.opMapEach({
      obj: inputNode,
      mapFn: Op.defineFunction(
        {row: Types.withNamedTag('run', 'run', 'any')},
        ({row}) =>
          Op.opPick({
            obj: frame.runColors,
            key: Op.opRunId({
              run: Op.opGetRunTag({obj: row as any}),
            }),
          })
      ),
    });
  }, [frame, inputNode]);
};
