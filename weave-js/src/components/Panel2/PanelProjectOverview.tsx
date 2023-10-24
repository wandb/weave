import {opProjectArtifacts, opProjectRuns} from '@wandb/weave/core';
import {
  opArtifactType,
  opArtifactTypeName,
  opCount,
  opProjectName,
  opRunJobtype,
  varNode,
} from '@wandb/weave/core';
import React, {useMemo} from 'react';

import * as CGReact from '../../react';
import * as KeyValTable from './KeyValTable';
import {LayoutTabs} from './LayoutTabs';
import * as Panel2 from './panel';
import {PanelComp2} from './PanelComp';
import {PanelNumber} from './PanelNumber';
import {PanelSpecs} from './PanelRegistry';
import {ProjectDashboardsTable} from './PanelRootBrowser/ProjectDashboardsTable';
import {ProjectObjectsTable} from './PanelRootBrowser/ProjectObjectsTable';
import * as TableState from './PanelTable/tableState';

const inputType = 'project' as const;
type PanelProjectOverviewProps = Panel2.PanelProps<typeof inputType>;

const useProjectObjectsExist = () => {
  // TODO
  return true;
};

const useProjectDashboardsExist = () => {
  // TODO
  return true;
};

const usePanelById = (id: string) => {
  return useMemo(() => {
    return PanelSpecs().find(spec => spec.id === id);
  }, [id]);
};

const PanelProjectOverviewNew: React.FC<
  PanelProjectOverviewProps & {isRoot?: boolean}
> = props => {
  const projectObjectsExist = useProjectObjectsExist();
  const projectDashboardExist = useProjectDashboardsExist();

  const dashboardsTabConfig = Panel2.useConfigChild(
    'dashboardsTab',
    props.config,
    props.updateConfig
  );

  const objectsTabConfig = Panel2.useConfigChild(
    'objectsTab',
    props.config,
    props.updateConfig
  );

  const runsTabConfig = Panel2.useConfigChild(
    'runsTab',
    props.config,
    props.updateConfig
  );

  const artifactsTabConfig = Panel2.useConfigChild(
    'runsTab',
    props.config,
    props.updateConfig
  );

  const tabNames = useMemo(() => {
    const names = [];
    if (props.isRoot && projectDashboardExist) {
      names.push('Dashboards');
    }
    if (projectObjectsExist) {
      names.push('Objects');
    }
    if (!props.isRoot) {
      names.push('Runs');
      names.push('Artifacts');
    }
    return names;
  }, [projectDashboardExist, projectObjectsExist, props.isRoot]);

  const runsRenderSpec = usePanelById('ProjectRunsTable');
  const runsNode = useMemo(() => {
    return opProjectRuns({project: props.input}) as any;
  }, [props.input]);

  const artifactsRenderSpec = usePanelById('ProjectArtifactsTable');
  const artifactsNode = useMemo(() => {
    return opProjectArtifacts({project: props.input}) as any;
  }, [props.input]);

  return (
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
              <ProjectDashboardsTable
                input={props.input}
                config={dashboardsTabConfig.config}
                updateConfig={dashboardsTabConfig.updateConfig}
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
              <ProjectObjectsTable
                input={props.input}
                config={objectsTabConfig.config}
                updateConfig={objectsTabConfig.updateConfig}
                context={props.context}
                updateContext={props.updateContext}
                updateInput={props.updateInput as any}
                isRoot={props.isRoot}
              />
            </div>
          );
        } else if (id === 'Runs') {
          return (
            <div
              style={{
                width: '100%',
                height: '100%',
              }}>
              {runsRenderSpec && (
                <PanelComp2
                  input={runsNode as any}
                  inputType={runsNode.type}
                  panelSpec={runsRenderSpec}
                  config={runsTabConfig.config}
                  updateConfig={runsTabConfig.updateConfig}
                  updateInput={props.updateInput}
                  updateContext={props.updateContext}
                  configMode={false}
                  context={props.context}
                />
              )}
            </div>
          );
        } else if (id === 'Artifacts') {
          return (
            <div
              style={{
                width: '100%',
                height: '100%',
              }}>
              {artifactsRenderSpec && (
                <PanelComp2
                  input={artifactsNode as any}
                  inputType={artifactsNode.type}
                  panelSpec={artifactsRenderSpec}
                  config={artifactsTabConfig.config}
                  updateConfig={artifactsTabConfig.updateConfig}
                  updateInput={props.updateInput}
                  updateContext={props.updateContext}
                  configMode={false}
                  context={props.context}
                />
              )}
            </div>
          );
        }
        return <></>;
      }}
    />
  );
};

const PanelProjectOverviewSimple: React.FC<
  PanelProjectOverviewProps
> = props => {
  const project = props.input;
  const projectName = opProjectName({project});
  const projectRuns = opProjectRuns({project});
  const projectRunsCount = opCount({
    arr: projectRuns,
  } as any);

  const projectArtifacts = opProjectArtifacts({project});
  const projectArtifactsCount = opCount({
    arr: projectArtifacts,
  } as any);

  // Build run job types table

  let runJobTypesTable = TableState.emptyTable();

  runJobTypesTable = TableState.appendEmptyColumn(runJobTypesTable);
  const jobTypeColId =
    runJobTypesTable.order[runJobTypesTable.order.length - 1];
  runJobTypesTable = TableState.updateColumnSelect(
    runJobTypesTable,
    jobTypeColId,
    opRunJobtype({run: varNode('run', 'row')})
  );

  runJobTypesTable = {...runJobTypesTable, groupBy: [jobTypeColId]};

  runJobTypesTable = TableState.appendEmptyColumn(runJobTypesTable);
  const runCountColId =
    runJobTypesTable.order[runJobTypesTable.order.length - 1];
  runJobTypesTable = TableState.updateColumnSelect(
    runJobTypesTable,
    runCountColId,
    opCount({
      arr: varNode({type: 'list', objectType: 'run'}, 'row') as any,
    })
  );

  // Build artifact types query

  let artifactTypesTable = TableState.emptyTable();

  artifactTypesTable = TableState.appendEmptyColumn(artifactTypesTable);
  const artifactTypeColId =
    artifactTypesTable.order[artifactTypesTable.order.length - 1];
  artifactTypesTable = TableState.updateColumnSelect(
    artifactTypesTable,
    artifactTypeColId,
    opArtifactTypeName({
      artifactType: opArtifactType({
        artifact: varNode('artifact', 'row'),
      }),
    })
  );

  artifactTypesTable = {...artifactTypesTable, groupBy: [artifactTypeColId]};

  artifactTypesTable = TableState.appendEmptyColumn(artifactTypesTable);
  const artifactCountColId =
    artifactTypesTable.order[artifactTypesTable.order.length - 1];
  artifactTypesTable = TableState.updateColumnSelect(
    artifactTypesTable,
    artifactCountColId,
    opCount({
      arr: varNode({type: 'list', objectType: 'artifact'}, 'row') as any,
    })
  );

  const projectNameQuery = CGReact.useNodeValue(projectName);
  const projectRunsQuery = CGReact.useNodeValue(projectRunsCount);
  const projectArtifactsQuery = CGReact.useNodeValue(projectArtifactsCount);
  if (
    projectNameQuery.loading ||
    projectRunsQuery.loading ||
    projectArtifactsQuery.loading
  ) {
    return <div>-</div>;
  }

  const inputVar = varNode(props.input.type, 'input');
  return (
    <KeyValTable.Table>
      <KeyValTable.Row>
        <KeyValTable.Key>
          <KeyValTable.InputUpdateLink
            onClick={() =>
              props.updateInput?.(opProjectRuns({project: inputVar}) as any)
            }>
            Runs
          </KeyValTable.InputUpdateLink>
        </KeyValTable.Key>
        <KeyValTable.Val>
          <PanelNumber
            input={projectRunsCount as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTable.Val>
      </KeyValTable.Row>
      <KeyValTable.Row>
        <KeyValTable.Key>
          <KeyValTable.InputUpdateLink
            onClick={() =>
              props.updateInput?.(
                opProjectArtifacts({project: inputVar}) as any
              )
            }>
            Artifacts
          </KeyValTable.InputUpdateLink>
        </KeyValTable.Key>
        <KeyValTable.Val>
          <PanelNumber
            input={projectArtifactsCount as any}
            context={props.context}
            updateContext={props.updateContext}
            // Get rid of updateConfig
            updateConfig={() => console.log('HELLO')}
          />
        </KeyValTable.Val>
      </KeyValTable.Row>
    </KeyValTable.Table>
  );
};

const PanelProjectOverview: React.FC<
  PanelProjectOverviewProps & {isRoot?: boolean}
> = props => {
  if (false) {
    return <PanelProjectOverviewNew {...props} />;
  }
  return <PanelProjectOverviewSimple {...props} />;
};

export {PanelProjectOverview};

export const Spec: Panel2.PanelSpec = {
  id: 'project-overview',
  Component: PanelProjectOverview,
  inputType,
};
