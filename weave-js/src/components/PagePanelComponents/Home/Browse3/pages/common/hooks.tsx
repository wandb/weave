import {useCallback, useState} from 'react';

import {useWeaveContext} from '../../../../../../context';
import {Node} from '../../../../../../core';
import {usePanelContext} from '../../../../../Panel2/PanelContext';
import {useMakeLocalBoardFromNode} from '../../../../../Panel2/pyBoardGen';
import {SEED_BOARD_OP_NAME} from '../../../HomePreviewSidebar';
import {useWeaveflowRouteContext} from '../../context';

export const useMakeNewBoard = (itemNode: Node) => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const [isGenerating, setIsGenerating] = useState(false);
  const {baseRouter} = useWeaveflowRouteContext();
  const onMakeBoard = useCallback(async () => {
    setIsGenerating(true);
    const refinedItemNode = await weave.refineNode(itemNode, stack);
    makeBoardFromNode(SEED_BOARD_OP_NAME, refinedItemNode, newDashExpr => {
      setIsGenerating(false);
      let exp = weave.expToString(newDashExpr);
      // remove all whitespace
      exp = exp.replace(/\s/g, '');
      // eslint-disable-next-line wandb/no-unprefixed-urls
      window.open(
        baseRouter.boardForExpressionUIUrl('', '', exp.trim()),
        '_blank'
      );
    });
  }, [baseRouter, itemNode, makeBoardFromNode, stack, weave]);
  return {onMakeBoard, isGenerating};
};
