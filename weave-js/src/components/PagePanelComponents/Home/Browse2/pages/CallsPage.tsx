import React from 'react';

import {useRunsWithFeedback} from '../callTreeHooks';
import {RunsTable} from '../RunsTable';
import {SimplePageLayout} from './common/SimplePageLayout';

export const CallsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const runs = useRunsWithFeedback(
    {
      entityName: props.entity,
      projectName: props.project,
      streamName: 'stream',
    },
    {}
  );
  return (
    <SimplePageLayout
      title="Calls"
      tabs={[
        {
          label: 'All',
          content: <RunsTable loading={runs.loading} spans={runs.result} />,
        },
      ]}
    />
  );
};
