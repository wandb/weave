/**
 * Link to a Weights & Biases Run.
 */
import {ApolloClient, gql, useApolloClient} from '@apollo/client';
import React, {useEffect, useState} from 'react';

import {LoadingDots} from '../../../LoadingDots';
import {RunLink} from '../../../RunLink';
import {
  CellFilterWrapper,
  OnUpdateFilter,
} from '../Browse3/filters/CellFilterWrapper';
import {NotApplicable} from '../Browse3/NotApplicable';

type CellValueRunProps = {
  entity: string;
  project: string;
  run: string; // "name" e.g. "dk6pv7ri"

  // These props are used for Option+Click support
  onUpdateFilter?: OnUpdateFilter;
  rowId: string;
};

const FIND_RUN_QUERY = gql`
  query FindRun(
    $entityName: String!
    $projectName: String!
    $runName: String!
  ) {
    project(name: $projectName, entityName: $entityName) {
      id
      internalId
      run(name: $runName) {
        id
        name
        displayName
      }
    }
  }
`;

type RunInfo = {
  projectInternalId: string;
  name: string;
  displayName: string;
};

type RunResult = 'load' | 'loading' | 'error' | RunInfo;

const fetchRun = (
  entityName: string,
  projectName: string,
  runName: string,
  apolloClient: ApolloClient<object>
) => {
  return apolloClient
    .query({
      query: FIND_RUN_QUERY as any,
      variables: {
        entityName,
        projectName,
        runName,
      },
    })
    .then(result => {
      const {project} = result.data;
      const {run} = project;
      return {
        projectInternalId: project.internalId,
        name: runName,
        displayName: run.displayName,
      };
    });
};

export const useRun = (
  entityName: string,
  projectName: string,
  runName: string
) => {
  const apolloClient = useApolloClient();

  const [runInfo, setRunInfo] = useState<RunResult>('load');
  useEffect(() => {
    let mounted = true;
    setRunInfo('loading');
    fetchRun(entityName, projectName, runName, apolloClient)
      .then(res => {
        if (!mounted) {
          return;
        }
        if (res === null) {
          setRunInfo('error');
          return;
        }
        setRunInfo(res);
      })
      .catch(err => {
        if (!mounted) {
          return;
        }
        console.error('Error fetching run data:', err);
        setRunInfo('error');
      });
    return () => {
      mounted = false;
    };
  }, [apolloClient, entityName, projectName, runName]);

  return runInfo;
};

export const CellValueRun = ({
  entity,
  project,
  run,
  onUpdateFilter,
  rowId,
}: CellValueRunProps) => {
  const runInfo = useRun(entity, project, run);

  if (runInfo === 'load' || runInfo === 'loading') {
    return <LoadingDots />;
  }
  if (runInfo === 'error') {
    return <NotApplicable />;
  }

  // Would be nice to show a run color indicator here but that requires getting information
  // out of the project view.

  const to = `/${entity}/${project}/runs/${run}`;
  const filterValue = runInfo.projectInternalId + ':' + runInfo.name;
  return (
    <CellFilterWrapper
      onUpdateFilter={onUpdateFilter}
      field="wb_run_id"
      rowId={rowId}
      operation="(string): equals"
      value={filterValue}>
      <RunLink
        entityName={entity}
        projectName={project}
        runName={run}
        to={to}
      />
    </CellFilterWrapper>
  );
};
