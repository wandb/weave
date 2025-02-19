import React from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../../../Button';
import {Icon} from '../../../../../../../Icon';
import {ThreadViewProps} from '../../types';
import {formatTimestamp} from '../TraceViews/utils';

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

const TimelineList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

const TimelineItem = styled(Button)<{$isSelected?: boolean}>`
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

const ItemContent = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
`;

export const TimelineView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traces,
  selectedTraceId,
  loading,
  error,
}) => {
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Icon name="loading" className="animate-spin" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-red-500">
        <Icon name="warning" className="mr-2" />
        <span>Error: {error.message}</span>
      </div>
    );
  }
  return (
    <Container>
      <ScrollContainer>
        <TimelineList>
          {traces.map(traceId => (
            <TimelineItem
              key={traceId}
              variant={traceId === selectedTraceId ? 'secondary' : 'ghost'}
              active={traceId === selectedTraceId}
              $isSelected={traceId === selectedTraceId}
              onClick={() => onTraceSelect(traceId)}>
              <ItemContent>
                <div className="truncate font-medium">{traceId}</div>
                <div className="truncate text-xs text-moon-500">
                  {formatTimestamp(new Date().toISOString())}
                </div>
              </ItemContent>
            </TimelineItem>
          ))}
        </TimelineList>
      </ScrollContainer>
    </Container>
  );
}; 