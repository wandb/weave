import {Node, WeaveInterface} from '@wandb/weave/core';

import {NodeAction} from '../../../actions';

export const ExpressionEditorActions = (
  weave: WeaveInterface,
  updateExp: (n: Node) => void
): NodeAction[] => {
  return [
    // Disabled for now because applying this to a table cell will put
    // hidden ops into the editor like createIndexCheckpoint, dropna, etc
    // {
    //   name: 'Set Editor Expression',
    //   icon: 'text cursor',
    //   isAvailable: () => true,
    //   doAction: (n, frame) => {
    //     updateExp(weave.callFunction(n, frame));
    //   },
    // },
  ];
};
