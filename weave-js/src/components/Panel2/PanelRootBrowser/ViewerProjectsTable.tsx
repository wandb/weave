import {useWeaveContext} from '@wandb/weave/context';
import {
  constFunction,
  constString,
  Node,
  opArray,
  opEntityName,
  opEntityProjects,
  opProjectName,
  opProjectUpdatedAt,
  opRootEntity,
  opRootProject,
  opRootViewer,
  opSort,
  opUserEntities,
  varNode,
  voidNode,
  WeaveInterface,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import {useMemo} from 'react';
import React from 'react';

import * as Panel2 from '../panel';
import {PanelCard} from '../PanelCard';
import {
  addNamedColumnToTable,
  emptyTable,
  getRowExampleNode,
} from '../PanelTable/tableState';

const makeTableState = (
  inputNode: Node,
  weave: WeaveInterface,
  entityName: string
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
  tableState = addNamedColumnToTable(tableState, 'Project Name', rowVar, {
    panelID: 'weavelink',
    panelConfig: {
      to: opRootProject({
        entityName: constString(entityName),
        projectName: varNode('string', 'input'),
      }),
      vars: {},
    },
  });

  return tableState;
};

const inputType = 'invalid';

type ViewerProjectsTableProps = Panel2.PanelProps<typeof inputType>;

export const ViewerProjectsTable: React.FC<
  ViewerProjectsTableProps
> = props => {
  const weave = useWeaveContext();

  const entityNameNode = useMemo(() => {
    return opEntityName({
      entity: opUserEntities({user: opRootViewer({})}),
    });
  }, []);
  const entitiesValue = useNodeValue(entityNameNode);
  const entities = useMemo(() => {
    return entitiesValue.result ?? [];
  }, [entitiesValue.result]);

  const cardConfig = Panel2.useConfigChild(
    'cardConfig',
    props.config,
    props.updateConfig,
    useMemo(
      () => ({
        title: constString(''),
        subtitle: 'Entity:',
        content: entities.map((entityName: string) => {
          const dataNode = opProjectName({
            project: opSort({
              arr: opEntityProjects({
                entity: opRootEntity({
                  entityName: constString(entityName),
                }),
              }),
              compFn: constFunction({row: 'project'}, ({row}) => {
                return opArray({
                  a: opProjectUpdatedAt({project: row}),
                } as any);
              }),
              columnDirs: opArray({
                a: constString('desc'),
              } as any),
            }),
          });
          return {
            name: entityName,
            content: {
              vars: {},
              input_node: dataNode,
              id: 'table',
              config: {
                simpleTable: true,
                tableState: makeTableState(dataNode, weave, entityName),
              },
            },
          };
        }),
      }),
      [entities, weave]
    )
  );

  if (entities.length === 0) {
    return <></>;
  }

  return (
    <PanelCard
      input={voidNode() as any}
      config={cardConfig.config}
      updateConfig={cardConfig.updateConfig}
      context={props.context}
      updateContext={props.updateContext}
      updateInput={props.updateInput as any}
    />
    // <PanelTable
    //   input={dataNode as any}
    //   config={tableConfig.config}
    //   updateConfig={tableConfig.updateConfig}
    //   context={props.context}
    //   updateContext={props.updateContext}
    //   updateInput={props.updateInput as any}
    // />
  );
};
