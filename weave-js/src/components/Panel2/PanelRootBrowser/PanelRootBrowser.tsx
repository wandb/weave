import {useIsAuthenticated} from '@wandb/weave/context/WeaveViewerContext';
import {
  constString,
  isConstNode,
  isOutputNode,
  Node,
  opRootProject,
  voidNode,
} from '@wandb/weave/core';
import _ from 'lodash';
import React, {useCallback, useMemo, useState} from 'react';
import {Icon} from 'semantic-ui-react';
import styled from 'styled-components';

import {isServedLocally} from '../../PagePanelComponents/util';
import {LayoutTabs} from '../LayoutTabs';
import * as Panel2 from '../panel';
import {usePanelContext} from '../PanelContext';
import {PanelProjectOverview} from '../PanelProjectOverview';
import {FrameVariablesTable} from './FrameVariablesTable';
import {LocalDashboardsTable} from './LocalDashboardsTable';
import {LocalObjectsTable, useLocalObjectsExist} from './LocalObjectsTable';
import {ViewerProjectsTable} from './ViewerProjectsTable';

const HIDE_VARIABLES_TAB = true;

const inputType = 'invalid';

type PanelRootBrowserProps = Panel2.PanelProps<typeof inputType>;

export const PanelRootBrowser: React.FC<
  PanelRootBrowserProps & {isRoot?: boolean}
> = props => {
  const servedLocally = isServedLocally();
  const localObjectsExist = useLocalObjectsExist();
  const isAuthenticated = useIsAuthenticated();
  const panelContext = usePanelContext();
  const variablesExist = useMemo(() => {
    return _.keys(panelContext.frame).length > 0;
  }, [panelContext.frame]);

  const dashboardsTabConfig = Panel2.useConfigChild(
    'localDashboardsTab',
    props.config,
    props.updateConfig
  );

  const frameVariablesTabConfig = Panel2.useConfigChild(
    'variablesTab',
    props.config,
    props.updateConfig
  );

  const objectsTabConfig = Panel2.useConfigChild(
    'objectsTab',
    props.config,
    props.updateConfig
  );

  const projectsTabConfig = Panel2.useConfigChild(
    'projectsTab',
    props.config,
    props.updateConfig
  );

  const projectScopeTabConfig = Panel2.useConfigChild(
    'projectScopeTab',
    props.config,
    props.updateConfig
  );

  const tabNames = useMemo(() => {
    const names = [];
    if (servedLocally) {
      if (props.isRoot) {
        names.push('Dashboards');
      }
      if (localObjectsExist) {
        names.push('Objects');
      }
    }
    if (isAuthenticated) {
      names.push('W&B Projects');
    }
    if (variablesExist && !HIDE_VARIABLES_TAB) {
      names.push('Variables');
    }
    return names;
  }, [
    servedLocally,
    localObjectsExist,
    props.isRoot,
    isAuthenticated,
    variablesExist,
  ]);

  const [selectedProject, setSelectedProject] = useState<
    | {
        entityName: string;
        projectName: string;
      }
    | undefined
  >(undefined);

  const updateInputProxyForProject = useCallback(
    (input: Node) => {
      if (
        props.isRoot &&
        isOutputNode(input) &&
        input.fromOp.name === 'root-project'
      ) {
        const entityNameNode = input.fromOp.inputs.entityName;
        const projectNameNode = input.fromOp.inputs.projectName;
        if (isConstNode(entityNameNode) && isConstNode(projectNameNode)) {
          setSelectedProject({
            entityName: entityNameNode.val,
            projectName: projectNameNode.val,
          });
          return;
        }
      }
      props.updateInput?.(input as any);
    },
    [props]
  );

  if (selectedProject) {
    return (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
        }}>
        <div
          style={{
            width: '100%',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
          <div
            style={{
              padding: 10,
              fontSize: 20,
              fontWeight: 'bold',
            }}>
            Project:&nbsp;{selectedProject.entityName}/
            {selectedProject.projectName}
          </div>
          <Icon
            onClick={() => {
              setSelectedProject(undefined);
            }}
            style={{
              lineHeight: '1.2rem',
              color: '#999',
              cursor: 'pointer',
            }}
            name="cancel"
          />
        </div>
        <PanelProjectOverview
          input={
            opRootProject({
              entityName: constString(selectedProject.entityName),
              projectName: constString(selectedProject.projectName),
            }) as any
          }
          config={projectScopeTabConfig.config}
          updateConfig={projectScopeTabConfig.updateConfig}
          context={props.context}
          updateContext={props.updateContext}
          updateInput={props.updateInput as any}
          isRoot={props.isRoot}
        />
      </div>
    );
  }

  return (
    <Container>
      {props.isRoot && (
        <Header>{servedLocally ? 'Local Weave Data' : 'Weave Data'}</Header>
      )}
      <LayoutTabs
        tabNames={tabNames}
        renderPanel={({id}) => {
          if (id === 'Dashboards') {
            return (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                }}>
                <LocalDashboardsTable
                  input={voidNode() as any}
                  config={dashboardsTabConfig.config}
                  updateConfig={dashboardsTabConfig.updateConfig}
                  context={props.context}
                  updateContext={props.updateContext}
                  updateInput={props.updateInput as any}
                />
              </div>
            );
          } else if (id === 'Variables') {
            return (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                }}>
                <FrameVariablesTable
                  input={voidNode() as any}
                  config={frameVariablesTabConfig.config}
                  updateConfig={frameVariablesTabConfig.updateConfig}
                  context={props.context}
                  updateContext={props.updateContext}
                  updateInput={props.updateInput as any}
                />
              </div>
            );
          } else if (id === 'Objects') {
            return (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                }}>
                <LocalObjectsTable
                  input={voidNode() as any}
                  config={objectsTabConfig.config}
                  updateConfig={objectsTabConfig.updateConfig}
                  context={props.context}
                  updateContext={props.updateContext}
                  updateInput={props.updateInput as any}
                  isRoot={props.isRoot}
                />
              </div>
            );
          } else if (id === 'W&B Projects') {
            return (
              <div
                style={{
                  width: '100%',
                  height: '100%',
                }}>
                <ViewerProjectsTable
                  input={voidNode() as any}
                  config={projectsTabConfig.config}
                  updateConfig={projectsTabConfig.updateConfig}
                  context={props.context}
                  updateContext={props.updateContext}
                  updateInput={updateInputProxyForProject as any}
                />
              </div>
            );
          }
          return <></>;
        }}
      />
    </Container>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'RootBrowser',
  Component: PanelRootBrowser,
  inputType,
};

const Container = styled.div`
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
`;

const Header = styled.div`
  margin-bottom: 24px;
  font-size: 20px;
  font-weight: 600;
`;
