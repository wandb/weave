import React from 'react';
import styled from 'styled-components';

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

const ChatList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 8px;
`;

const ChatItem = styled.div<{$isSelected?: boolean}>`
  display: flex;
  flex-direction: column;
  gap: 1px;
  border: 1px solid ${props => (props.$isSelected ? '#3B82F6' : '#E2E8F0')};
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: all 0.15s ease;
  overflow: hidden;

  &:hover {
    border-color: ${props => (props.$isSelected ? '#3B82F6' : '#CBD5E1')};
    background: ${props => (props.$isSelected ? '#EFF6FF' : '#F8FAFC')};
  }
`;

const InputSection = styled.div`
  padding: 12px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
`;

const OutputSection = styled.div`
  padding: 12px;
`;

const Label = styled.div`
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
  margin-bottom: 4px;
`;

const Content = styled.div`
  font-size: 13px;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
`;

export const ChatView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traces,
  selectedTraceId,
  loading,
  error,
}) => {
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-moon-500">Loading traces...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-red-500">
        Error: {error.message}
      </div>
    );
  }

  return (
    <Container>
      <ScrollContainer>
        <ChatList>
          {traces.map(traceId => (
            <ChatItem
              key={traceId}
              $isSelected={traceId === selectedTraceId}
              onClick={() => onTraceSelect(traceId)}>
              <InputSection>
                <Label>Input</Label>
                <Content>
                  This is a placeholder input message for trace {traceId}. It
                  could contain multiple lines of text and show the actual input
                  parameters.
                </Content>
              </InputSection>
              <OutputSection>
                <Label>Output</Label>
                <Content>
                  This is a placeholder output message for trace {traceId}. It
                  would show the actual result or response from the trace
                  execution.
                </Content>
              </OutputSection>
            </ChatItem>
          ))}
        </ChatList>
      </ScrollContainer>
    </Container>
  );
};
