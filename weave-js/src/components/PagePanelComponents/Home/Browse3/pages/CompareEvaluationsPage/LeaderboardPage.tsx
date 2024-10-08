import React, {useState} from 'react';
import styled from 'styled-components';

import {SimplePageLayout} from '../common/SimplePageLayout';
import {EditableMarkdown} from './EditableMarkdown';
import {fakeLeaderboardData} from './fakeData';
import {LeaderboardGrid} from './LeaderboardGrid';
import {LeaderboardHeader} from './LeaderboardHeader';

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
    <LeaderboardContainer>
      <DescriptionArea>
        <EditableMarkdown
          value={description}
          onChange={setDescription}
          placeholder="Add a description for this leaderboard..."
        />
      </DescriptionArea>
      <LeaderboardGrid data={data} onCellClick={handleCellClick} />
    </LeaderboardContainer>
  );
};

const LeaderboardContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  background-color: #f5f5f5;
`;

const DescriptionArea = styled.div`
  background-color: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
`;
