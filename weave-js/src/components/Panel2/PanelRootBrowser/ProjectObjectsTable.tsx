import {useWeaveContext} from '@wandb/weave/context';
import {
  constString,
  Node,
  opArtifactType,
  opArtifactTypeArtifacts,
  opArtifactTypeName,
  opProjectArtifacts,
  opProjectArtifactType,
  opUnique,
  voidNode,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import React, {useCallback, useMemo} from 'react';
import styled from 'styled-components';

import * as Panel2 from '../panel';
import {PanelCard} from '../PanelCard';
import {PanelContextProvider} from '../PanelContext';
import {
  artifactsNodeToDisplayNameNode,
  makeTableState,
} from './ProjectDashboardsTable';
import {
  opFilterArtifactsToWeaveObjects,
  useCopiedVariableName,
  useNewPanelFromRootQueryCallback,
} from './util';

const useUniqueTypeNames = (projectNode: Node) => {
  const unique = opUnique({
    arr: opArtifactTypeName({
      artifactType: opArtifactType({
        artifact: opFilterArtifactsToWeaveObjects(
          opProjectArtifacts({project: projectNode})
        ),
      }),
    }),
  });
  return useNodeValue(unique).result ?? [];
};

const getDataNode = (projectNode: Node, typeName: string) => {
  const filteredArtifactsNode = opFilterArtifactsToWeaveObjects(
    opArtifactTypeArtifacts({
      artifactType: opProjectArtifactType({
        project: projectNode,
        artifactType: constString(typeName),
      }),
    })
  );
  return artifactsNodeToDisplayNameNode(filteredArtifactsNode);
};

const inputType = 'project';

type ProjectObjectsTableProps = Panel2.PanelProps<typeof inputType>;

export const ProjectObjectsTable: React.FC<
  ProjectObjectsTableProps & {isRoot?: boolean}
> = props => {
  const weave = useWeaveContext();
  const typenames = useUniqueTypeNames(props.input);

  const {newExpr, newFrame} = useCopiedVariableName(props.input, 'input');

  const tableState = useMemo(() => {
    return makeTableState(weave, newExpr);
  }, [newExpr, weave]);

  const makeNewDashboard = useNewPanelFromRootQueryCallback();

  const updateInputProxy = useCallback(
    (newInput: Node) => {
      const updateInput = props.updateInput;
      if (updateInput != null) {
        if (props.isRoot) {
          const name = 'dashboard-temp-view';
          makeNewDashboard(name, newInput, false, newDashExpr => {
            updateInput(newDashExpr as any);
          });
        } else {
          updateInput(newInput as any);
        }
      }
    },
    [makeNewDashboard, props]
  );

  const cardConfig = Panel2.useConfigChild(
    'cardConfig',
    props.config,
    props.updateConfig,
    useMemo(
      () => ({
        title: constString('Objects'),
        subtitle: '',
        content: typenames.map((typename: string) => {
          return {
            name: typename,
            content: {
              vars: {},
              input_node: getDataNode(newExpr, typename),
              id: 'table',
              config: {
                simpleTable: true,
                tableState,
              },
            },
          };
        }),
      }),
      [newExpr, tableState, typenames]
    )
  );

  if (typenames.length === 0) {
    return <EmptyStateContainer>No objects found</EmptyStateContainer>;
  }

  return (
    <PanelContextProvider newVars={newFrame}>
      <PanelCard
        input={voidNode() as any}
        config={cardConfig.config}
        updateConfig={cardConfig.updateConfig}
        context={props.context}
        updateContext={props.updateContext}
        updateInput={updateInputProxy as any}
      />
    </PanelContextProvider>
  );
};

const EmptyStateContainer = styled.div`
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
`;
EmptyStateContainer.displayName = 'S.EmptyStateContainer';
