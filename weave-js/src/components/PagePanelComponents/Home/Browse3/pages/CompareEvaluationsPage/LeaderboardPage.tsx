import React, {useState} from 'react';
import {Box, Divider} from '@mui/material';

import {SimplePageLayout} from '../common/SimplePageLayout';
import {EditableMarkdown} from './EditableMarkdown';
import {fakeLeaderboardData} from './fakeData';
import {LeaderboardGrid} from './LeaderboardGrid';

type LeaderboardPageProps = {
  entity: string;
  project: string;
};

export const LeaderboardPage: React.FC<LeaderboardPageProps> = props => {
  return (
    <SimplePageLayout
      title={`${props.project} Leaderboard`}
      hideTabsIfSingle
      tabs={[
        {
          label: 'Results',
          content: (
            <LeaderboardPageContent
              entity={props.entity}
              project={props.project}
            />
          ),
        },
      ]}
    />
  );
};

export const LeaderboardPageContent: React.FC<LeaderboardPageProps> = props => {
  const [description, setDescription] = useState(
    'Welcome to the Leaderboard! Compare model performance across different metrics.'
  );
  const [data] = useState(fakeLeaderboardData);

  const handleCellClick = (
    modelName: string,
    metricName: string,
    score: number
  ) => {
    console.log(`Clicked on ${modelName} for ${metricName}: ${score}%`);
    // TODO: Implement action on cell click
  };

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <Box mb={2}>
        <EditableMarkdown
          value={description}
          onChange={setDescription}
          placeholder="Add a description for this leaderboard..."
        />
      </Box>
      <Divider />
      <Box flexGrow={1} mt={2}>
        <LeaderboardGrid data={data} onCellClick={handleCellClick} />
      </Box>
    </Box>
  );
};
