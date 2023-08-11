// This file provides utilities for generating dashboards.
import {
  callOpVeryUnsafe,
  constNone,
  constString,
  dereferenceAllVars,
  Node,
  opGet,
  Type,
  voidNode,
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

export const OPENAI_BOARD_OP_NAME = 'py_board-openai_monitor_board';

interface StreamTableObj {
  entity_name: string;
  project_name: string;
  table_name: string;
  hints?: {
    integrations: string[];
  };
}

export const _getStreamTableObjFromRowsNode = (node: Node) => {
  if (node.nodeType === 'output' && node.fromOp.name === 'stream_table-rows') {
    return node.fromOp.inputs.self;
  }
  return voidNode();
};

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
  const streamTableObjNode = _getStreamTableObjFromRowsNode(node);
  const streamTableObjValue = useNodeValue(streamTableObjNode);
  const streamTableObj = streamTableObjValue.result as StreamTableObj | null;

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
      config: Type | null;
    }>;
  } = useNodeValue(genBoardsNode as any);
  return useMemo(() => {
    if (res.loading || streamTableObjValue.loading) {
      return {loading: true, result: []};
    } else {
      const finalResult = res.result.filter(x => allowConfig || !x.config);
      if (
        streamTableObj &&
        streamTableObj.hints?.integrations.includes('openai') &&
        !finalResult.find(x => x.op_name === OPENAI_BOARD_OP_NAME)
      ) {
        finalResult.push({
          display_name: 'OpenAI Monitor Board',
          description: 'Monitor OpenAI Completions',
          op_name: OPENAI_BOARD_OP_NAME,
          config: null,
        });
      }
      console.log('FINAL RESULT', finalResult);
      return {
        loading: false,
        result: finalResult,
      };
    }
  }, [
    allowConfig,
    res.loading,
    res.result,
    streamTableObj,
    streamTableObjValue.loading,
  ]);
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
