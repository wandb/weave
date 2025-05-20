/**
 * Select a Run from within a Project.
 */
import {gql, useApolloClient} from '@apollo/client';
import {Select} from '@wandb/weave/components/Form/Select';
import _ from 'lodash';
import React, {useEffect, useState} from 'react';

export type RunOption = {
  // e.g. "UHJvamVjdEludGVybmFsSWQ6NDE2OTQ4MDc= which decodes to "ProjectInternalId:41694807"
  // This is useful for constructing the value we store in ClickHouse.
  // Since this query is project scoped, this value should be constant across options,
  // but is repeated for ease of use.
  projectInternalId: string;

  value: string; // run name, e.g. "qd58mkmj"

  displayName: string; // e.g. "restful-glitter-3"
};

type SelectRunProps = {
  entityName: string;
  projectName: string;
  runName?: string;
  onSelectRun: (run: RunOption) => void;
};

const FETCH_PROJECT_RUNS_QUERY = gql`
  query FetchProjectRuns($entityName: String!, $projectName: String!) {
    project(entityName: $entityName, name: $projectName) {
      id
      internalId
      runs {
        edges {
          node {
            id
            name
            displayName
          }
        }
      }
    }
  }
`;

const getRunOptions = (result: any): RunOption[] => {
  const projectInternalId = result?.data?.project?.internalId ?? '';
  const edges = result?.data?.project?.runs?.edges ?? [];
  const options = edges.map((edge: any) => {
    const run = edge.node;
    return {
      value: run.name,
      displayName: run.displayName,
      projectInternalId,
    };
  });
  return options;
};

const labelStyle = {
  whiteSpace: 'nowrap' as const,
};

const formatOptionLabel = (option: RunOption) => {
  return <div style={labelStyle}>{option.displayName}</div>;
};

type RunResult = 'load' | 'loading' | 'error' | RunOption[];

export const useProjectRuns = (entityName: string, projectName: string) => {
  const apolloClient = useApolloClient();

  const [runs, setRuns] = useState<RunResult>('load');
  useEffect(() => {
    let mounted = true;
    setRuns('loading');
    apolloClient
      .query({
        query: FETCH_PROJECT_RUNS_QUERY as any,
        variables: {
          entityName,
          projectName,
        },
      })
      .then(runRes => {
        if (!mounted) {
          return;
        }
        setRuns(getRunOptions(runRes));
      })
      .catch(err => {
        if (!mounted) {
          return;
        }
        setRuns('error');
      });
    return () => {
      mounted = false;
    };
  }, [apolloClient, entityName, projectName]);

  return runs;
};

export const SelectRun = ({
  entityName,
  projectName,
  runName,
  onSelectRun,
}: SelectRunProps) => {
  const runs = useProjectRuns(entityName, projectName);
  if (runs === 'load' || runs === 'loading' || runs === 'error') {
    return null;
  }

  const selectedOption = _.find(runs, o => o.value === runName);
  const onChange = (option: RunOption | null) => {
    if (option) {
      onSelectRun(option);
    }
  };

  return (
    <Select<RunOption>
      options={runs}
      placeholder="Select a run..."
      value={selectedOption}
      formatOptionLabel={formatOptionLabel}
      onChange={onChange}
    />
  );
};
