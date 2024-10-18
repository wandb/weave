import React from 'react';
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
                <QueueName>{queue.name}</QueueName>
                <QueueDescription>{queue.description}</QueueDescription>
                <TracesCount>
                  {queue.modelsEvaluated} Models Evaluated
                </TracesCount>
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
              <QueueName>{queue.name}</QueueName>
              <QueueDescription>{queue.description}</QueueDescription>
              <TracesCount>
                {queue.modelsEvaluated} Models Evaluated
              </TracesCount>
            </QueueCard>
          ))}
        </QueueGrid>
      </Section>
    </Container>
  );
};

const Container = styled.div`
  padding: 20px;
`;

const Header = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
`;

const Title = styled.h1`
  font-size: 24px;
  margin: 0;
`;

const CreateQueueButton = styled.button`
  background-color: #00a4b8;
  color: white;
  border: none;
  padding: 10px 15px;
  border-radius: 4px;
  cursor: pointer;
`;

const WelcomeMessage = styled.div`
  background-color: #f0f0f0;
  padding: 10px;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
`;

const DismissButton = styled.button`
  background: none;
  border: none;
  color: #00a4b8;
  cursor: pointer;
`;

const Section = styled.div`
  margin-bottom: 20px;
`;

const SectionTitle = styled.h2`
  font-size: 18px;
  margin-bottom: 10px;
`;

const QueueGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 20px;
`;

const QueueCard = styled.div`
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 15px;
`;

const QueueName = styled.h3`
  font-size: 16px;
  margin: 0 0 10px 0;
`;

const ReviewButton = styled.button`
  background-color: #ffa500;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 4px;
  cursor: pointer;
  float: right;
`;

const QueueDescription = styled.p`
  font-size: 14px;
  color: #666;
  margin: 0 0 10px 0;
`;

const TracesCount = styled.div`
  font-size: 24px;
  font-weight: bold;
`;
