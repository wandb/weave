// This file provides utilities for generating dashboards.
import {
  callOpVeryUnsafe,
  constNone,
  constString,
  dereferenceAllVars,
  isConstNode,
  isOutputNode,
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

const getRootURIFromNode = (node: Node) => {
  while (isOutputNode(node)) {
    const inputs = Object.values(node.fromOp.inputs);
    if (inputs.length === 0) {
      return null;
    } else if (
      node.fromOp.name === 'get' &&
      isConstNode(node.fromOp.inputs.uri)
    ) {
      return '' + node.fromOp.inputs.uri.val;
    }
    node = inputs[0];
  }
  return null;
};

export const getNameFromURI = (uri: string) => {
  let parts = uri.split('://');
  if (parts.length !== 2) {
    return null;
  }
  parts = parts[1].split(':')[0].split('/');
  return parts[parts.length - 1];
};

const getNameFromRootURINode = (node: Node) => {
  const uri = getRootURIFromNode(node);
  if (uri) {
    return getNameFromURI(uri);
  }
  return null;
};

const getNameFromRootArtifactNode = (node: Node) => {
  while (isOutputNode(node)) {
    const inputs = Object.values(node.fromOp.inputs);
    if (inputs.length === 0) {
      return null;
    } else if (
      node.fromOp.name === 'project-artifact' &&
      isConstNode(node.fromOp.inputs.artifactName)
    ) {
      const name = '' + node.fromOp.inputs.artifactName.val;
      if (name.startsWith('run-')) {
        const parts = name.split('-');
        return parts[parts.length - 1];
      }
    }
    node = inputs[0];
  }
  return null;
};

const getNameFromNodeHeuristic = (node: Node) => {
  let name = getNameFromRootURINode(node);
  if (name == null) {
    name = getNameFromRootArtifactNode(node);
  }
  if (name) {
    name = name.toLowerCase().replace(/[^a-z0-9]/g, '_');
  }
  return name;
};

const makeBoardName = (
  boardGenOpName: string,
  inputNode: Node,
  boardName?: string
) => {
  if (boardName != null) {
    return boardName;
  }
  let objectName = getNameFromNodeHeuristic(inputNode) ?? '';
  if (objectName) {
    objectName = objectName + '-';
  }
  const boardNameMap: {[name: string]: string} = {
    'py_board-llm_completions_monitor': 'llm_completion_analysis',
    'py_board-seed_autoboard': 'timeseries_analysis',
  };
  const prefix = boardNameMap[boardGenOpName] || 'board';

  const suffix = moment().format('YY_MM_DD_hh_mm_ss');
  return `${objectName}${prefix}-${suffix}`;
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
      boardName = makeBoardName(boardGenOpName, inputNode, boardName);
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
