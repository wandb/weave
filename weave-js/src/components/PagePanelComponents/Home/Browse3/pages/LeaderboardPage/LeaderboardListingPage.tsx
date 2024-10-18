import { Box } from '@material-ui/core';
import { Button } from '@wandb/weave/components/Button/Button';
import React, { FC } from 'react';
import styled from 'styled-components';

import {Empty} from '../common/Empty';
import {
  EMPTY_PROPS_EVALUATIONS,
  EMPTY_PROPS_LEADERBOARDS,
} from '../common/EmptyContent';
import {SimplePageLayout} from '../common/SimplePageLayout';

export const LeaderboardListingPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  return (
    <SimplePageLayout
      title={`Leaderboards`}
      hideTabsIfSingle
      tabs={[
        {
          label: 'All',
          content: <LeaderboardListingPageInner {...props} />,
        },
      ]}
      headerExtra={<CreateLeaderboardButton/>}
    />
  );
};

export const LeaderboardListingPageInner: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const customLeaderboards = [
    {
      name: 'Weather_genApp_experts',
      description: 'This is the description',
      modelsEvaluated: '16',
    },
    {
      name: 'TidePressure_modeling_team',
      description: 'This is the description',
      modelsEvaluated: '30',
    },
    {
      name: 'ClimateModel_genApp_experts',
      description: 'This is the description',
      modelsEvaluated: '15',
    },
    {
      name: 'OceanCurrent_analysis_team',
      description: 'This is the description',
      modelsEvaluated: '70',
    },
    {
      name: 'Windflow_projection_experts',
      description: 'This is the description',
      modelsEvaluated: '82',
    },
    {
      name: 'AtmoMetrics_analysis_team',
      description: 'This is the description',
      modelsEvaluated: '40',
    },
    {
      name: 'HydroFluor_research_specialists',
      description: 'This is the description',
      modelsEvaluated: '202',
    },
  ];

  const evalBoards = [
    {
      name: 'Weather_genApp_experts',
      description: 'This is the description',
      modelsEvaluated: '16',
    },
    {
      name: 'TidePressure_modeling_team',
      description: 'This is the description',
      modelsEvaluated: '30',
    },
    {
      name: 'ClimateModel_genApp_experts',
      description: 'This is the description',
      modelsEvaluated: '15',
    },
    {
      name: 'OceanCurrent_analysis_team',
      description: 'This is the description',
      modelsEvaluated: '70',
    },
    {
      name: 'Windflow_projection_experts',
      description: 'This is the description',
      modelsEvaluated: '82',
    },
    {
      name: 'AtmoMetrics_analysis_team',
      description: 'This is the description',
      modelsEvaluated: '40',
    },
    {
      name: 'HydroFluor_research_specialists',
      description: 'This is the description',
      modelsEvaluated: '202',
    },
  ];

  const hasCustomLeaderboards = customLeaderboards.length > 0;
  const hasEvalLeaderboards = evalBoards.length > 0;
  const allEmpty = !hasCustomLeaderboards && !hasEvalLeaderboards;

  return allEmpty ? (
    <Empty {...EMPTY_PROPS_EVALUATIONS} />
  ) : (
    <Container>
      <Section>
        <SectionTitle>Custom Leaderboards ({customLeaderboards.length})</SectionTitle>
        {!hasCustomLeaderboards ? (
          <Empty {...EMPTY_PROPS_LEADERBOARDS} />
        ) : (
          <QueueGrid>
            {customLeaderboards.map(queue => (
              <QueueCard key={queue.name}>
                <LeaderboardName>{queue.name}</LeaderboardName>
                <LeaderboardDescription>{queue.description}</LeaderboardDescription>
                <ModelCount>
                  {queue.modelsEvaluated} models
                </ModelCount>
              </QueueCard>
            ))}
          </QueueGrid>
        )}
      </Section>
      <Section>
        <SectionTitle>Evaluation Leaderboards ({evalBoards.length})</SectionTitle>
        <QueueGrid>
          {evalBoards.map(queue => (
            <QueueCard key={queue.name}>
              <LeaderboardName>{queue.name}</LeaderboardName>
              <LeaderboardDescription>{queue.description}</LeaderboardDescription>
              <ModelCount>
                {queue.modelsEvaluated} models
              </ModelCount>
            </QueueCard>
          ))}
        </QueueGrid>
      </Section>
    </Container>
  );
};

const Container = styled.div`
  padding: 16px;
  width: 100%;
  height: 100%;
  overflow: auto;
`;



const CreateLeaderboardButton: FC = (
) => {
  return (
    <Box
      sx={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
      }}>
      <Button
        className="mx-16"
        style={{
          marginLeft: '0px',
        }}
        size="medium"
        variant="secondary"
        onClick={console.log}
        icon="add-new">
        Create Leaderboard
      </Button>
    </Box>
  );
};


const Section = styled.div`
  margin-top: 0px;
  margin-bottom: 30px;
`;

const SectionTitle = styled.h2`
  font-size: 18px;
  margin-bottom: 10px;
`;

const QueueGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 24px;
`;

const QueueCard = styled.div`
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 20px;
  transition: all 0.3s ease;
  cursor: pointer;
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);

  &:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    border-color: #00A4B8;
  }
`;

const LeaderboardName = styled.h3`
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 12px 0;
  color: #00A4B8;
`;

const LeaderboardDescription = styled.p`
  font-size: 14px;
  color: #666;
  margin: 0 0 16px 0;
  line-height: 1.4;
`;

const ModelCount = styled.div`
  font-size: 16px;
  font-weight: 600;
  color: #333;
`;
