import {useWeaveContext} from '@wandb/weave/context';
import {
  constFunction,
  constNode,
  list,
  Node,
  opArtifactName,
  opEntityName,
  opGet,
  opMap,
  opProjectArtifacts,
  opProjectEntity,
  opProjectName,
  varNode,
  WeaveInterface,
} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import * as Panel2 from '../panel';
import {PanelContextProvider} from '../PanelContext';
import {PanelTable} from '../PanelTable/PanelTable';
import {
  addNamedColumnToTable,
  emptyTable,
  getRowExampleNode,
} from '../PanelTable/tableState';
import {
  opFilterArtifactsToWeaveObjects,
  opStringConcat,
  useCopiedVariableName,
} from './util';

export const makeTableState = (weave: WeaveInterface, projectNode: Node) => {
  let tableState = emptyTable();
  const exNode = getRowExampleNode(
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    constNode(list('string'), []),
    weave
  );
  const rowVar = varNode(exNode.type, 'row');

  tableState = addNamedColumnToTable(tableState, 'Dashboard Name', rowVar, {
    panelID: 'weavelink',
    panelConfig: {
      to: opGet({
        uri: varNode('string', 'uri_str'),
      }),
      vars: {
        uri_str: opStringConcat(
          'wandb-artifact:///',
          opEntityName({entity: opProjectEntity({project: projectNode})}),
          '/',
          opProjectName({project: projectNode}),
          '/',
          varNode('string', 'input'),
          ':latest',
          // TODO: We sort of cheat by putting the commit hash in the data row. This is not ideal
          // as I would rather hide that, but the backend executor is super inefficient at resolving
          // this class of graph when in a table (dozens of network requests)
          // ':',
          // opArtifactMembershipCommitHash({
          //   artifactMembership: opArtifactMembershipForAlias({
          //     artifact: opProjectArtifact({
          //       project: projectNode,
          //       artifactName: varNode('string', 'input'),
          //     }),
          //     aliasName: constString('latest'),
          //   }),
          // }),
          '/obj'
        ),
      },
    },
  });
  return tableState;
};

export const artifactsNodeToDisplayNameNode = (artifactsNode: Node) => {
  // Once the above hack is fixed, we can just do this:
  // return opArtifactName({artifact: filteredArtifactsNode})
  return opMap({
    arr: artifactsNode,
    mapFn: constFunction({row: 'artifact'}, ({row}) => {
      return opArtifactName({artifact: row});
      // return opStringConcat(
      //   opArtifactName({artifact: row}),
      //   ':',
      //   opArtifactMembershipCommitHash({
      //     artifactMembership: opArtifactMembershipForAlias({
      //       artifact: row,
      //       aliasName: constString('latest'),
      //     }),
      //   })
      // );
    }),
  });
};

const getDataNode = (projectNode: Node) => {
  const filteredArtifactsNode = opFilterArtifactsToWeaveObjects(
    opProjectArtifacts({project: projectNode}),
    true
  );

  return artifactsNodeToDisplayNameNode(filteredArtifactsNode);
};

const inputType = 'project';

type ProjectDashboardsTableProps = Panel2.PanelProps<typeof inputType>;

export const ProjectDashboardsTable: React.FC<
  ProjectDashboardsTableProps
> = props => {
  const weave = useWeaveContext();
  const {newExpr, newFrame} = useCopiedVariableName(props.input, 'input');

  const dataNode = useMemo(() => getDataNode(newExpr), [newExpr]);

  const tableState = useMemo(() => {
    return makeTableState(weave, newExpr);
  }, [newExpr, weave]);

  const tableConfig = Panel2.useConfigChild(
    'tableConfig',
    props.config,
    props.updateConfig,
    useMemo(
      () => ({
        simpleTable: true,
        tableState,
      }),
      [tableState]
    )
  );

  return (
    <PanelContextProvider newVars={newFrame}>
      <PanelTable
        input={dataNode as any}
        config={tableConfig.config}
        updateConfig={tableConfig.updateConfig}
        context={props.context}
        updateContext={props.updateContext}
        updateInput={props.updateInput as any}
      />
    </PanelContextProvider>
  );
};
