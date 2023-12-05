import {urlPrefixed} from '@wandb/weave/config';
import React, {useCallback, useState} from 'react';

import {useWeaveContext} from '../../../../../../context';
import {Node} from '../../../../../../core';
import {usePanelContext} from '../../../../../Panel2/PanelContext';
import {useMakeLocalBoardFromNode} from '../../../../../Panel2/pyBoardGen';
import {SEED_BOARD_OP_NAME} from '../../../HomePreviewSidebar';

export const useMakeNewBoard = (itemNode: Node) => {
  const weave = useWeaveContext();
  const {stack} = usePanelContext();
  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const [isGenerating, setIsGenerating] = useState(false);
  const onMakeBoard = useCallback(async () => {
    setIsGenerating(true);
    const refinedItemNode = await weave.refineNode(itemNode, stack);
    makeBoardFromNode(SEED_BOARD_OP_NAME, refinedItemNode, newDashExpr => {
      setIsGenerating(false);
      window.open(
        urlPrefixed('/?exp=' + weave.expToString(newDashExpr)),
        '_blank'
      );
    });
  }, [itemNode, makeBoardFromNode, stack, weave]);
  return {onMakeBoard, isGenerating};
};
