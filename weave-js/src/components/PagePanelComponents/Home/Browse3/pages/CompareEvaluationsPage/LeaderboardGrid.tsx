import React from 'react';
import styled from 'styled-components';

interface LeaderboardGridProps {
  data: {
    models: string[];
    metrics: string[];
    scores: {[key: string]: {[key: string]: number}};
  };
  onCellClick: (modelName: string, metricName: string, score: number) => void;
}

export const LeaderboardGrid: React.FC<LeaderboardGridProps> = ({
  data,
  onCellClick,
}) => (
  <GridContainer>
    <GridHeader>
      <HeaderCell>Model</HeaderCell>
      {data.metrics.map(metric => (
        <HeaderCell key={metric}>{metric}</HeaderCell>
      ))}
    </GridHeader>
    {data.models.map(model => (
      <GridRow key={model}>
        <ModelCell>{model}</ModelCell>
        {data.metrics.map(metric => (
          <ScoreCell
            key={`${model}-${metric}`}
            onClick={() =>
              onCellClick(model, metric, data.scores[model][metric])
            }
            score={data.scores[model][metric]}>
            {data.scores[model][metric].toFixed(2)}%
          </ScoreCell>
        ))}
      </GridRow>
    ))}
  </GridContainer>
);

const GridContainer = styled.div`
  background-color: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
`;

const GridHeader = styled.div`
  display: grid;
  grid-template-columns: 200px repeat(auto-fit, minmax(100px, 1fr));
  background-color: #34495e;
  color: white;
  font-weight: bold;
`;

const HeaderCell = styled.div`
  padding: 16px;
  text-align: center;
`;

const GridRow = styled.div`
  display: grid;
  grid-template-columns: 200px repeat(auto-fit, minmax(100px, 1fr));
  &:nth-child(even) {
    background-color: #f8f9fa;
  }
`;

const ModelCell = styled.div`
  padding: 16px;
  font-weight: bold;
`;

const ScoreCell = styled.div<{score: number}>`
  padding: 16px;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.2s;
  background-color: ${props => `hsl(${120 * (props.score / 100)}, 70%, 80%)`};
  &:hover {
    background-color: ${props => `hsl(${120 * (props.score / 100)}, 70%, 70%)`};
  }
`;
