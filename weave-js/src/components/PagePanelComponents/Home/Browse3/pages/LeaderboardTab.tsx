import {Box} from '@mui/material';
import React from 'react';

import {LeaderboardGrid} from '../views/Leaderboard/LeaderboardGrid';
import {useLeaderboardData} from '../views/Leaderboard/query/hookAdapters';

type EvaluationLeaderboardTabProps = {
  entity: string;
  project: string;
  evaluationObjectName: string;
  evaluationObjectVersion: string;
};

export const EvaluationLeaderboardTab: React.FC<
  EvaluationLeaderboardTabProps
> = props => {
  const {entity, project, evaluationObjectName, evaluationObjectVersion} =
    props;

  const {loading, data} = useLeaderboardData(entity, project, {
    sourceEvaluations: [
      {
        name: evaluationObjectName,
        version: evaluationObjectVersion,
      },
    ],
  });

  return (
    <Box
      display="flex"
      flexDirection="row"
      height="100%"
      flexGrow={1}
      overflow="hidden">
      <LeaderboardGrid
        entity={entity}
        project={project}
        loading={loading}
        data={data}
      />
    </Box>
  );
};
