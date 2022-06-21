import React from 'react';
import {Header} from 'semantic-ui-react';
import * as Panel2 from './panel';
import * as Op from '@wandb/cg/browser/ops';
import * as CG from '@wandb/cg/browser/graph';
import * as CGReact from '@wandb/common/cgreact';
import * as TableState from './PanelTable/tableState';
import {PanelComp2} from './PanelComp';
// import {Spec as PanelTable2Spec} from './PanelTable2';
import {Spec as PanelSimpleTableSpec} from './PanelSimpleTable';
// import {Spec as PanelSuperPlotSpec} from './PanelPlot';

const inputType = 'project' as const;
type PanelProjectOverviewProps = Panel2.PanelProps<typeof inputType>;

const PanelProjectOverview: React.FC<PanelProjectOverviewProps> = props => {
  const project = props.input;
  const projectName = Op.opProjectName({project});
  const projectRuns = Op.opProjectRuns({project});
  const projectRunsCount = Op.opCount({
    arr: projectRuns,
  } as any);

  const projectArtifacts = Op.opProjectArtifacts({project});
  const projectArtifactsCount = Op.opCount({
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
    Op.opRunJobtype({run: CG.varNode('run', 'row')})
  );

  runJobTypesTable = {...runJobTypesTable, groupBy: [jobTypeColId]};

  runJobTypesTable = TableState.appendEmptyColumn(runJobTypesTable);
  const runCountColId =
    runJobTypesTable.order[runJobTypesTable.order.length - 1];
  runJobTypesTable = TableState.updateColumnSelect(
    runJobTypesTable,
    runCountColId,
    Op.opCount({
      arr: CG.varNode({type: 'list', objectType: 'run'}, 'row') as any,
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
    Op.opArtifactTypeName({
      artifactType: Op.opArtifactType({
        artifact: CG.varNode('artifact', 'row'),
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
    Op.opCount({
      arr: CG.varNode({type: 'list', objectType: 'artifact'}, 'row') as any,
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

  return (
    <div>
      <Header as="h3">Project: {projectNameQuery.result}</Header>
      <div style={{display: 'flex', justifyContent: 'space-between'}}>
        <div style={{flexGrow: 1}}>
          <b>Runs</b>
          <div>Count: {projectRunsQuery.result}</div>
          {/* <div>
            {tableNodeQuery.result.map((row: any) => {
              let {jobtype, count} = row;
              return (
                <div>
                  <span
                    onClick={() => {
                      console.log('click');
                    }}>
                    {jobtype}
                  </span>
                  : {count}
                </div>
              );
            })}
          </div> */}
          {/* <pre>{toString(tableNode)}</pre>
          <pre>{JSON.stringify(tableNodeQuery.result, undefined, 2)}</pre> */}
          <div style={{marginRight: 24}}>
            <PanelComp2
              input={projectRuns as any}
              inputType={projectRuns.type}
              loading={false}
              panelSpec={PanelSimpleTableSpec}
              configMode={false}
              context={props.context}
              config={runJobTypesTable}
              updateConfig={() => {
                console.log('projectoverview table updateConfig');
              }}
              updateContext={props.updateContext}
            />
          </div>
          {/* <PanelComp2
            input={projectRuns as any}
            inputType={projectRuns.type}
            loading={false}
            panelSpec={PanelSuperPlotSpec}
            configMode={false}
            context={props.context}
            config={{
              table: runJobTypesTable,
              dims: {y: jobTypeColId, x: countColId},
              title: 'job types',
              yAxisLabel: '',
            }}
            updateConfig={() => {
              console.log('projectoverview table updateConfig');
            }}
            updateContext={props.updateContext}
          /> */}
        </div>
        <div style={{flexGrow: 1}}>
          <b>Artifacts</b>
          <div>Count: {projectArtifactsQuery.result}</div>
          {/* <div>
            {tableNodeQuery.result.map((row: any) => {
              let {jobtype, count} = row;
              return (
                <div>
                  <span
                    onClick={() => {
                      console.log('click');
                    }}>
                    {jobtype}
                  </span>
                  : {count}
                </div>
              );
            })}
          </div> */}
          {/* <pre>{toString(tableNode)}</pre>
          <pre>{JSON.stringify(tableNodeQuery.result, undefined, 2)}</pre> */}
          <div style={{marginRight: 24}}>
            <PanelComp2
              input={projectArtifacts as any}
              inputType={projectArtifacts.type}
              loading={false}
              panelSpec={PanelSimpleTableSpec}
              configMode={false}
              context={props.context}
              config={artifactTypesTable}
              updateConfig={() => {
                console.log('projectoverview table updateConfig');
              }}
              updateContext={props.updateContext}
            />
          </div>
          {/* <PanelComp2
            input={projectRuns as any}
            inputType={projectRuns.type}
            loading={false}
            panelSpec={PanelSuperPlotSpec}
            configMode={false}
            context={props.context}
            config={{
              table: runJobTypesTable,
              dims: {y: jobTypeColId, x: countColId},
              title: 'job types',
              yAxisLabel: '',
            }}
            updateConfig={() => {
              console.log('projectoverview table updateConfig');
            }}
            updateContext={props.updateContext}
          /> */}
        </div>
      </div>
    </div>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'project-overview',
  Component: PanelProjectOverview,
  inputType,
};
