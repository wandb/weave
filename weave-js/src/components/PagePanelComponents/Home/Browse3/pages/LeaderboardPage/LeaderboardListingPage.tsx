import React from 'react';
import styled from 'styled-components';

import { Empty } from '../common/Empty';
import { EMPTY_PROPS_EVALUATIONS } from '../common/EmptyContent';

export const LeaderboardListingPage: React.FC<{
  entity: string;
  project: string;
}> = ({entity, project}) => {
  const annotationQueues = [
    { name: 'Weather_genApp_experts', description: 'This is the description', traces: '16/45', needsReview: true },
    { name: 'TidePressure_modeling_team', description: 'This is the description', traces: '30/62', needsReview: true },
    { name: 'ClimateModel_genApp_experts', description: 'This is the description', traces: '15', needsReview: false },
    { name: 'OceanCurrent_analysis_team', description: 'This is the description', traces: '70', needsReview: false },
    { name: 'Windflow_projection_experts', description: 'This is the description', traces: '82', needsReview: false },
    { name: 'AtmoMetrics_analysis_team', description: 'This is the description', traces: '40', needsReview: false },
    { name: 'HydroFluor_research_specialists', description: 'This is the description', traces: '202', needsReview: false },
  ];

  return (
    <Container>
      <Header>
        <Title>Annotation queues</Title>
        <CreateQueueButton>+ Create queue</CreateQueueButton>
      </Header>
      <WelcomeMessage>
        Welcome to annotation queues
        <DismissButton>Dismiss</DismissButton>
      </WelcomeMessage>
      <Section>
        <SectionTitle>Needs review (2)</SectionTitle>
        <QueueGrid>
          {annotationQueues.filter(queue => queue.needsReview).map(queue => (
            <QueueCard key={queue.name}>
              <QueueName>{queue.name}</QueueName>
              <ReviewButton>Review</ReviewButton>
              <QueueDescription>{queue.description}</QueueDescription>
              <TracesCount>{queue.traces} Traces</TracesCount>
            </QueueCard>
          ))}
        </QueueGrid>
      </Section>
      <Section>
        <SectionTitle>Up to date (5)</SectionTitle>
        <QueueGrid>
          {annotationQueues.filter(queue => !queue.needsReview).map(queue => (
            <QueueCard key={queue.name}>
              <QueueName>{queue.name}</QueueName>
              <QueueDescription>{queue.description}</QueueDescription>
              <TracesCount>{queue.traces} Traces</TracesCount>
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
  background-color: #00A4B8;
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
  color: #00A4B8;
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
  background-color: #FFA500;
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

const NoEvaluations = () => {
  return <Empty {...EMPTY_PROPS_EVALUATIONS} />;
};
