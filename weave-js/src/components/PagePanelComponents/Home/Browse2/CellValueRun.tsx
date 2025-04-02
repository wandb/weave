/**
 * Link to a Weights & Biases Run.
 */
import {ApolloClient, gql, useApolloClient} from '@apollo/client';
import React, {useEffect, useState} from 'react';

import {LoadingDots} from '../../../LoadingDots';
import {NotApplicable} from '../Browse3/NotApplicable';
import {Link} from '../Browse3/pages/common/Links';

type CellValueRunProps = {
  entity: string;
  project: string;
  run: string; // "name" e.g. "dk6pv7ri"
};

const FIND_RUN_QUERY = gql`
  query FindRun(
    $entityName: String!
    $projectName: String!
    $runName: String!
  ) {
    project(name: $projectName, entityName: $entityName) {
      run(name: $runName) {
        id
        name
        displayName
      }
    }
  }
`;

type RunInfo = {
  id: string;
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
      return result.data.project.run as RunInfo;
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

export const CellValueRun = ({entity, project, run}: CellValueRunProps) => {
  const runInfo = useRun(entity, project, run);

  if (runInfo === 'load' || runInfo === 'loading') {
    return <LoadingDots />;
  }
  if (runInfo === 'error') {
    return <NotApplicable />;
  }

  const to = `/${entity}/${project}/runs/${run}`;
  // Would be nice to show a run color indicator here but that requires getting information
  // out of the project view.
  return <Link to={to}>{runInfo.displayName}</Link>;
};
