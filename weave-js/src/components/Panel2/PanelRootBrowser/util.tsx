import {
  callOpVeryUnsafe,
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
  opFilter,
  opGet,
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

import {usePanelContext} from '../PanelContext';
import {toWeaveType} from '../toWeaveType';
import {
  ensureDashboard,
  ensureDashboardFromItems,
  ensureSimpleDashboard,
  PanelTreeNode,
} from '../panelTree';
import {
  emptyTable,
  getRowExampleNode,
  addNamedColumnToTable,
} from '../PanelTable/tableState';
import {ChildPanelFullConfig} from '../ChildPanel';

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
    arr: callOpVeryUnsafe(
      'op-local_artifacts',
      {},
      {type: 'list', objectType: {type: 'FilesystemArtifact' as any}}
    ) as any,
    mapFn: constFunction(
      {row: {type: 'FilesystemArtifact' as any}},
      ({row}) => {
        return callOpVeryUnsafe(
          'FilesystemArtifact-getLatestVersion',
          {artifact: row},
          {type: 'FilesystemArtifact' as any}
        ) as any;
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
      const metadataObj = callOpVeryUnsafe(
        'FilesystemArtifact-metadata',
        {
          self: row,
        },
        {type: 'typedDict', propertyTypes: {}}
      ) as any;
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
        const nameNode = callOpVeryUnsafe(
          'FilesystemArtifact-artifactName',
          {
            artifact: row,
          },
          'string'
        ) as any;
        const versionNode = callOpVeryUnsafe(
          'FilesystemArtifact-artifactVersion',
          {
            artifact: row,
          },
          'string'
        ) as any;
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
