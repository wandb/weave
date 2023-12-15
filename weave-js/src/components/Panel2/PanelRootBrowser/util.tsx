import {
  constBoolean,
  constFunction,
  constNodeUnsafe,
  constString,
  dereferenceAllVars,
  expressionVariables,
  Node,
  NodeOrVoidNode,
  opAnd,
  opArtifactMembershipArtifactVersion,
  opArtifactMembershipForAlias,
  opArtifactVersionMetadata,
  opBooleanEqual,
  opFilesystemArtifactArtifactName,
  opFilesystemArtifactArtifactVersion,
  opFilesystemArtifactLatestVersion,
  opFilesystemArtifactMetadata,
  opFilter,
  opGet,
  opLocalArtifacts,
  opMap,
  opPick,
  opStringAdd,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import {
  absoluteTargetMutation,
  makeMutation,
  useClientContext,
  useRefreshAllNodes,
} from '@wandb/weave/react';
import _ from 'lodash';
import {useCallback, useMemo} from 'react';

import {ChildPanelFullConfig} from '../ChildPanel';
import {usePanelContext} from '../PanelContext';
import {
  addNamedColumnToTable,
  emptyTable,
  getRowExampleNode,
} from '../PanelTable/tableState';
import {
  ensureDashboard,
  ensureDashboardFromItems,
  ensureSimpleDashboard,
  PanelTreeNode,
} from '../panelTree';
import {toWeaveType} from '../toWeaveType';

export const useCopiedVariableName = (
  expr: Node,
  origName: string,
  newName?: string
) => {
  const {frame} = usePanelContext();

  if (!newName) {
    const numVars = Object.keys(frame).length;
    newName = `input_${numVars}`;
  }

  const needsReplacement = useMemo(() => {
    return (
      _.filter(expressionVariables(expr), v => v.varName === origName).length >
      0
    );
  }, [expr, origName]);

  const newExpr = useMemo(() => {
    if (needsReplacement) {
      const newInput = _.cloneDeep(expr);
      _.filter(expressionVariables(newInput), v => v.varName === origName).map(
        v => (v.varName = newName as string)
      );
      return newInput;
    }
    return expr;
  }, [expr, needsReplacement, newName, origName]);

  return {
    newExpr,
    newFrame: needsReplacement
      ? {
          [newName]: frame[origName],
        }
      : {},
  };
};

export const useNewPanelFromRootQueryCallback = () => {
  const refreshAll = useRefreshAllNodes();
  const {stack, triggerExpressionEvent} = usePanelContext();
  const {client} = useClientContext();
  // const newDashMutation = useMutation(newDashExpr, 'set');
  const makeNewDashboard = useCallback(
    async (
      panelName: string,
      rootQuery: PanelTreeNode,
      dashboardLayout?: boolean,
      onCreated?: (newPanel: Node) => void
    ) => {
      if (client) {
        const target = opGet({
          uri: constString(`local-artifact:///${panelName}:latest/obj`),
        });
        const absoluteTarget = dereferenceAllVars(target, stack).node;
        const {rootArgs, mutationStyle, rootType} =
          absoluteTargetMutation(absoluteTarget);
        const newDashMutation = makeMutation(
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
        let panelConstructor = ensureSimpleDashboard;
        if (dashboardLayout) {
          panelConstructor = ensureDashboard;
        }
        const panelConfig = panelConstructor(rootQuery);
        await newDashMutation({
          val: constNodeUnsafe(toWeaveType(panelConfig), panelConfig),
        });
        if (onCreated) {
          onCreated(target);
        }
      }
    },
    [client, refreshAll, stack, triggerExpressionEvent]
  );
  return makeNewDashboard;
};

export const useNewDashFromItems = () => {
  const refreshAll = useRefreshAllNodes();
  const {stack, triggerExpressionEvent} = usePanelContext();
  const {client} = useClientContext();
  // const newDashMutation = useMutation(newDashExpr, 'set');
  const makeNewDashboard = useCallback(
    async (
      panelName: string,
      items: {[name: string]: ChildPanelFullConfig},
      vars: {[name: string]: NodeOrVoidNode},
      onCreated?: (newPanel: Node) => void
    ) => {
      if (client) {
        const target = opGet({
          uri: constString(`local-artifact:///${panelName}:latest/obj`),
        });
        const absoluteTarget = dereferenceAllVars(target, stack).node;
        const {rootArgs, mutationStyle, rootType} =
          absoluteTargetMutation(absoluteTarget);
        const newDashMutation = makeMutation(
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
        const panelConfig = ensureDashboardFromItems(items, vars);
        await newDashMutation({
          val: constNodeUnsafe(toWeaveType(panelConfig), panelConfig),
        });
        if (onCreated) {
          onCreated(target);
        }
      }
    },
    [client, refreshAll, stack, triggerExpressionEvent]
  );
  return makeNewDashboard;
};

const ensureStringNode = (node: Node | string) => {
  if (typeof node === 'string') {
    return constString(node);
  }
  return node;
};

export const opStringConcat = (...args: Array<Node | string>) => {
  let curr = ensureStringNode(args[0]);
  for (let i = 1; i < args.length; i++) {
    curr = opStringAdd({
      lhs: curr,
      rhs: ensureStringNode(args[i]),
    });
  }
  return curr;
};

export const opFilterArtifactsToWeaveObjects = (
  artifactsNode: Node,
  isPanel: boolean = false
) => {
  return opFilter({
    arr: artifactsNode,
    filterFn: constFunction({row: 'artifact'}, ({row}) => {
      return opBooleanEqual({
        lhs: opPick({
          obj: opArtifactVersionMetadata({
            artifactVersion: opArtifactMembershipArtifactVersion({
              artifactMembership: opArtifactMembershipForAlias({
                artifact: row,
                aliasName: constString('latest'),
              }),
            }),
          }),
          key: constString('_weave_meta.is_panel'),
        }),
        rhs: constBoolean(isPanel),
      });
    }),
  });
};

const opLatestLocalArtifacts = () => {
  return opMap({
    arr: opLocalArtifacts({}),
    mapFn: constFunction(
      {row: {type: 'FilesystemArtifact' as any}},
      ({row}) => {
        return opFilesystemArtifactLatestVersion({
          artifact: row as Node<{type: 'FilesystemArtifact'}>,
        });
      }
    ),
  });
};

const opFilterFilesystemArtifactsToWeaveObjects = (
  artifactsNode: Node,
  isPanel: boolean = false
) => {
  return opFilter({
    arr: artifactsNode,
    filterFn: constFunction({row: 'FilesystemArtifact' as any}, ({row}) => {
      const metadataObj = opFilesystemArtifactMetadata({
        self: row as Node<{type: 'FilesystemArtifact'}>,
      });
      const isWeaveObj = opBooleanEqual({
        lhs: opPick({
          obj: metadataObj,
          key: constString('_weave_meta.is_weave_obj'),
        }),
        rhs: constBoolean(true),
      });
      const isPanelNode = opBooleanEqual({
        lhs: opPick({
          obj: metadataObj,
          key: constString('_weave_meta.is_panel'),
        }),
        rhs: constBoolean(isPanel),
      });
      return opAnd({
        lhs: isWeaveObj,
        rhs: isPanelNode,
      });
    }),
  });
};

export const getLocalArtifactDataNode = (isPanel?: boolean) => {
  return opFilterFilesystemArtifactsToWeaveObjects(
    opLatestLocalArtifacts(),
    isPanel
  );
};

export const opObjectsToName = (allObjectsNode: Node) => {
  return opMap({
    arr: allObjectsNode,
    mapFn: constFunction(
      {row: {type: 'FilesystemArtifact' as any}},
      ({row}) => {
        const nameNode = opFilesystemArtifactArtifactName({
          artifact: row as Node<{type: 'FilesystemArtifact'}>,
        });
        const versionNode = opFilesystemArtifactArtifactVersion({
          artifact: row as Node<{type: 'FilesystemArtifact'}>,
        });
        return opStringConcat(nameNode, ':', versionNode);
      }
    ),
  });
};

export const opObjectNameToURI = (opName: Node) =>
  opStringConcat('local-artifact:///', opName, '/obj');

export const getLocalArtifactDataTableState = (
  inputNode: Node,
  colName: string,
  weave: WeaveInterface
) => {
  let tableState = emptyTable();
  const exNode = getRowExampleNode(
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    inputNode,
    weave
  );
  const rowVar = varNode(exNode.type, 'row');

  tableState = addNamedColumnToTable(tableState, colName, rowVar, {
    panelID: 'weavelink',
    panelConfig: {
      to: opGet({
        uri: varNode('string', 'uri_str'),
      }),
      vars: {
        uri_str: opObjectNameToURI(varNode(exNode.type, 'input')),
      },
    },
  });
  return tableState;
};
