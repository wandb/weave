import React from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../../../Button';
import {ThreadViewProps} from '../../types';

const Container = styled.div`
  height: 100%;
  overflow: hidden;
  background: #f8fafc;
`;

const ScrollContainer = styled.div`
  height: 100%;
  overflow-y: auto;
  padding: 8px;
`;

const ThreadList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const ThreadItem = styled(Button)<{$isSelected?: boolean}>`
  width: 100%;
  justify-content: flex-start;
  padding: 8px 12px;
  border: 1px solid ${props => (props.$isSelected ? '#3B82F6' : '#E2E8F0')};
  border-radius: 4px;
  background: ${props => (props.$isSelected ? '#EFF6FF' : 'white')};
  transition: all 0.15s ease;
  
  &:hover {
    background: ${props => (props.$isSelected ? '#DBEAFE' : '#F8FAFC')};
    border-color: ${props => (props.$isSelected ? '#3B82F6' : '#CBD5E1')};
  }

  &:active {
    transform: scale(0.995);
  }
`;

export const ListView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traces,
  selectedTraceId,
  loading,
  error,
}) => {
  if (loading) {
    return <div className="p-4">Loading traces...</div>;
  }
  if (error) {
    return <div className="p-4 text-red-500">Error: {error.message}</div>;
  }
  return (
    <Container>
      <ScrollContainer>
        <ThreadList>
          {traces.map(traceId => (
            <ThreadItem
              key={traceId}
              variant={traceId === selectedTraceId ? 'secondary' : 'ghost'}
              active={traceId === selectedTraceId}
              $isSelected={traceId === selectedTraceId}
              onClick={() => onTraceSelect(traceId)}>
              <span className="truncate font-medium">{traceId}</span>
            </ThreadItem>
          ))}
        </ThreadList>
      </ScrollContainer>
    </Container>
  );
}; 