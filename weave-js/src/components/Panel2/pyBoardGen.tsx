// This file provides utilities for generating dashboards.
import {
  callOpVeryUnsafe,
  constNone,
  constString,
  dereferenceAllVars,
  Node,
  opGet,
} from '@wandb/weave/core';
import {
  absoluteTargetMutation,
  makeMutation,
  useClientContext,
  useRefreshAllNodes,
} from '@wandb/weave/react';
import {useCallback} from 'react';

import {usePanelContext} from './PanelContext';
import moment from 'moment';

export const useMakeLocalBoardFromNode = () => {
  const simpleSetter = useMakeSimpleSetMutation();
  return useCallback(
    (
      boardGenOpName: string,
      inputNode: Node,
      onCreated: (newPanel: Node) => void,
      boardName?: string,
      config: Node = constNone()
    ) => {
      if (!boardName) {
        boardName = 'board-' + moment().format('YY_MM_DD_hh_mm_ss');
      }
      simpleSetter(
        `local-artifact:///${boardName}:latest/obj`,
        callOpVeryUnsafe(
          boardGenOpName,
          {input_node: inputNode, config},
          'any' as const
        ) as any,
        onCreated
      );
    },
    [simpleSetter]
  );
};

// The whole mutation system in react.tsx is insanely complicated.
// This function attempts to reduce the complexity to just what
// most callers need.
const useMakeSimpleSetMutation = () => {
  const refreshAll = useRefreshAllNodes();
  const {stack, triggerExpressionEvent} = usePanelContext();
  const {client} = useClientContext();
  return useCallback(
    async (
      targetURI: string,
      setValueFromNode: Node,
      onCreated?: (newPanel: Node) => void
    ) => {
      if (client) {
        const target = opGet({
          uri: constString(targetURI),
        });
        const absoluteTarget = dereferenceAllVars(target, stack).node;
        const {rootArgs, mutationStyle, rootType} =
          absoluteTargetMutation(absoluteTarget);
        const mutation = makeMutation(
          target,
          'set',
          refreshAll,
          stack,
          triggerExpressionEvent,
          absoluteTarget,
          mutationStyle,
          rootArgs,
          rootType,
          client,
          onCreated
        );
        await mutation({
          val: setValueFromNode,
        });
      }
    },
    [client, refreshAll, stack, triggerExpressionEvent]
  );
};
