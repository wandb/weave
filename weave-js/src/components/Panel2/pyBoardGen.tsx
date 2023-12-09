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
  opGetFeaturedBoardTemplatesForNode,
  Type,
} from '@wandb/weave/core';
import {
  absoluteTargetMutation,
  makeMutation,
  useClientContext,
  useMakeMutation,
  useNodeValue,
  useRefreshAllNodes,
} from '@wandb/weave/react';
import moment from 'moment';
import {useCallback, useMemo} from 'react';

import {uriFromNode} from '../PagePanelComponents/util';
import {usePanelContext} from './PanelContext';

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
  const genBoardsNode = opGetFeaturedBoardTemplatesForNode({
    input_node: node,
  });
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
    } else if (node.fromOp.name === 'get') {
      return uriFromNode(node);
    }
    node = inputs[0];
  }
  return null;
};

export const getNamePartFromURI = (uri: string) => {
  let parts = uri.split('://');
  if (parts.length !== 2) {
    return null;
  }
  parts = parts[1].split(':')[0].split('/');
  return parts[parts.length - 1];
};

export const getPartsFromURI = (uri: string) => {
  const parts = uri.split('://');
  if (parts.length !== 2) {
    return null;
  }
  const artifactName = parts[1].split(':')[0];
  const entityProjectNameList = artifactName.split('/');
  return entityProjectNameList;
};

const getNameFromRootURINode = (node: Node) => {
  const uri = getRootURIFromNode(node);
  if (uri) {
    return getNamePartFromURI(uri);
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

const getNameFromLoggedTrace = (node: Node) => {
  while (isOutputNode(node)) {
    if (node.fromOp.name === 'wb_trace_tree-convertToSpans') {
      const pickNode = node.fromOp.inputs.tree;
      if (isOutputNode(pickNode) && pickNode.fromOp.name === 'pick') {
        const nameNode = pickNode.fromOp.inputs.key;
        if (isConstNode(nameNode)) {
          return nameNode.val;
        }
      }
      return null;
    }
    const inputs = Object.values(node.fromOp.inputs);
    node = inputs[0];
  }
  return null;
};

const sanitizeName = (name: string) => {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '_');
};

const getNameFromNodeHeuristic = (node: Node) => {
  let name = getNameFromRootURINode(node);
  if (name == null) {
    name = getNameFromRootArtifactNode(node);
  }
  if (name == null) {
    name = getNameFromLoggedTrace(node);
  }
  if (name) {
    return sanitizeName(name);
  }
  return null;
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

export function useMakePublicBoardFromNode() {
  const makeBoardFromNode = useMakeLocalBoardFromNode();
  const makeMutation2 = useMakeMutation();

  return useCallback(
    (
      inputNode: Node,
      onCreated: (newPanel: Node) => void,
      boardTemplate: string,
      boardName?: string,
      projectName?: string,
      entityName?: string
    ) => {
      boardName = makeBoardName(boardTemplate, inputNode, boardName);
      if (!(entityName && projectName)) {
        const uri = getRootURIFromNode(inputNode);
        if (!uri) {
          return null;
        }
        const parts = getPartsFromURI(uri);
        if (!parts) {
          return null;
        }
        entityName = parts[0];
        projectName = parts[1];
      }

      return makeBoardFromNode(boardTemplate, inputNode, draftNode => {
        makeMutation2(
          draftNode,
          'publish_artifact',
          {
            artifact_name: constString(boardName!),
            project_name: constString(projectName!),
            entity_name: constString(entityName!),
          },
          publishedNode => {
            onCreated(publishedNode as any);
          }
        );
      });
    },
    [makeBoardFromNode, makeMutation2]
  );
}

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
