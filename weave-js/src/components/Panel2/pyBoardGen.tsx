// This file provides utilities for generating dashboards.
import {
  callOpVeryUnsafe,
  constNodeUnsafe,
  constNone,
  constString,
  dereferenceAllVars,
  Node,
  opGet,
  Type,
} from '@wandb/weave/core';
import {
  absoluteTargetMutation,
  makeMutation,
  useClientContext,
  useNodeValue,
  useRefreshAllNodes,
} from '@wandb/weave/react';
import {useCallback, useMemo} from 'react';

import {usePanelContext} from './PanelContext';
import moment from 'moment';

export const useBoardGeneratorsForNode = (
  node: Node,
  allowConfig: boolean = false
): {
  loading: boolean;
  result: Array<{
    display_name: string;
    description: string;
    op_name: string;
  }>;
} => {
  const genBoardsNode = callOpVeryUnsafe(
    'py_board-get_board_templates_for_node',
    {
      input_node: node,
    }
  );
  const res: {
    loading: boolean;
    result: Array<{
      display_name: string;
      description: string;
      op_name: string;
      config: Type;
    }>;
  } = useNodeValue(genBoardsNode as any);
  return useMemo(() => {
    if (res.loading) {
      return {loading: true, result: []};
    } else {
      return {
        loading: false,
        result: res.result.filter(x => allowConfig || !x.config),
      };
    }
  }, [allowConfig, res.loading, res.result]);
};

const makeFrozenConstFunction = (node: Node) => {
  console.log('FREEXING', node);
  return node;
  const innerType: Type = {
    type: 'function',
    inputTypes: {},
    outputType: node.type,
  };
  return constNodeUnsafe(innerType, node, true);
};

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
          {input_node: makeFrozenConstFunction(inputNode), config},
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
