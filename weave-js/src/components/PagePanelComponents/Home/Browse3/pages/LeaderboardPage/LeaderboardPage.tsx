import {Box} from '@mui/material';
import React, {useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../../context';
import {EditableMarkdown} from './EditableMarkdown';
import {useLeaderboardData} from './hooks';
import {LeaderboardGrid} from './LeaderboardGrid';

const USE_COMPARE_EVALUATIONS_PAGE = false;

type LeaderboardPageProps = {
  entity: string;
  project: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  return (
    <LeaderboardPageContent entity={props.entity} project={props.project} />
  );
};

const DEFAULT_DESCRIPTION = `# Leaderboard`;

export const LeaderboardPageContent: React.FC<LeaderboardPageProps> = props => {
  const {entity, project} = props;
  const [description, setDescription] = useState('');
  const {loading, data} = useLeaderboardData(entity, project);

  // const setDescription = useCallback((newDescription: string) => {
  //   setDescriptionRaw(newDescription.trim());
  // }, []);

  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  const handleCellClick = (
    modelName: string,
    metricName: string,
    score: number
  ) => {
    const sourceCallId = data.scores?.[modelName]?.[metricName]?.sourceCallId;
    if (sourceCallId) {
      let to: string;
      if (USE_COMPARE_EVALUATIONS_PAGE) {
        to = peekingRouter.compareEvaluationsUri(entity, project, [
          sourceCallId,
        ]);
      } else {
        to = peekingRouter.callUIUrl(entity, project, '', sourceCallId, null);
      }
      history.push(to);
    }
  };

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <Box flexShrink={0} maxHeight="50%" overflow="auto">
        <EditableMarkdown
          value={description}
          onChange={setDescription}
          placeholder={DEFAULT_DESCRIPTION}
        />
      </Box>
      <Box
        flexGrow={1}
        display="flex"
        flexDirection="column"
        overflow="hidden"
        minHeight="50%">
        <LeaderboardGrid
          loading={loading}
          data={data}
          onCellClick={handleCellClick}
        />
      </Box>
    </Box>
  );
};
