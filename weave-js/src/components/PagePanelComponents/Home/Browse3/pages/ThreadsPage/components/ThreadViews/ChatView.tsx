import React, {useMemo, useState} from 'react';
import styled from 'styled-components';

import {Button} from '../../../../../../../Button';
import {Icon} from '../../../../../../../Icon';
import {useWFHooks} from '../../../wfReactInterface/context';
import {TraceCallSchema} from '../../../wfReactInterface/traceServerClientTypes';
import {ThreadViewProps} from '../../types';

const Container = styled.div`
  height: 100%;
  overflow: hidden;

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
  background: ${props => (props.$isSelected ? '#EFF6FF' : 'white')};
  cursor: pointer;
  transition: all 0.15s ease;
  overflow: hidden;

  &:hover {
    border-color: ${props => (props.$isSelected ? '#3B82F6' : '#94A3B8')};
  }
`;

const Section = styled.div`
  padding: 0;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  position: relative;
`;

const SectionHeader = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8fafc;
  position: sticky;
  top: 0;
  z-index: 1;
  border-bottom: 1px solid #e2e8f0;

  /* Add shadow when content is scrolled */
  &::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: -1px;
    height: 4px;
    background: linear-gradient(180deg, rgba(0, 0, 0, 0.05), transparent);
    opacity: 0;
    transition: opacity 0.2s;
  }
  
  &[data-scrolled="true"]::after {
    opacity: 1;
  }
`;

const Label = styled.div`
  font-size: 11px;
  font-weight: 500;
  color: #64748b;
`;

const ContentWrapper = styled.div`
  padding: 12px;
  padding-top: 0;
`;

const Content = styled.div<{$isExpanded: boolean}>`
  font-size: 13px;
  color: #0f172a;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: ${props => (props.$isExpanded ? 'none' : '100px')};
  overflow-y: auto;
  transition: max-height 0.15s ease;
  position: relative;

  &::-webkit-scrollbar {
    width: 8px;
  }

  &::-webkit-scrollbar-track {
    background: transparent;
  }

  &::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 4px;
  }

  &::-webkit-scrollbar-thumb:hover {
    background: #94A3B8;
  }
`;

const ExpandButton = styled(Button)`
  padding: 2px 6px !important;
  height: auto !important;
  min-height: 0 !important;
`;

export const ChatView: React.FC<ThreadViewProps> = ({
  onTraceSelect,
  traceRoots,
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
          {traceRoots.map(traceRoot => (
            <ChatRow
              key={traceRoot.id}
              traceRootCall={traceRoot}
              selectedTraceId={selectedTraceId}
              onTraceSelect={onTraceSelect}
            />
          ))}
        </ChatList>
      </ScrollContainer>
    </Container>
  );
};

// const processRecursively = (obj: any, fn: (key: string, value: any) => any) => {
//   for (const key in obj) {
//     if (obj.hasOwnProperty(key)) {
//         obj[key] = fn(key, processRecursively(obj[key], fn));
//     }
//   }
//   return obj;
// };

// const removeUnderscoredKeys = (obj: any) => {
//   return processRecursively(obj, (key, value) => {
//     if (key.startsWith('_')) {
//       return undefined;
//     }
//     return value;
//   });
// };

// const removeEmptyValues = (obj: any) => {
//   return processRecursively(obj, (key, value) => {
//     if (value === undefined || value === null) {
//       return undefined;
//     }
//     return value;
//   });
// };


// const processInput = (input: any) => {
//   return removeUnderscoredKeys(removeEmptyValues(input));
// };

// const processOutput = (output: any) => {
//   return removeUnderscoredKeys(removeEmptyValues(output));
// };

function ChatRow({
  traceRootCall,
  selectedTraceId,
  onTraceSelect,
}: {
  traceRootCall: TraceCallSchema;
  selectedTraceId: string | undefined;
  onTraceSelect: (traceId: string) => void;
}) {
  const {useCall} = useWFHooks();
  const [isInputExpanded, setIsInputExpanded] = useState(false);
  const [isOutputExpanded, setIsOutputExpanded] = useState(false);
  const [isInputScrolled, setIsInputScrolled] = useState(false);
  const [isOutputScrolled, setIsOutputScrolled] = useState(false);
  const inputContentRef = React.useRef<HTMLDivElement>(null);
  const outputContentRef = React.useRef<HTMLDivElement>(null);

  const handleScroll = (
    event: React.UIEvent<HTMLDivElement>,
    setScrolled: (scrolled: boolean) => void
  ) => {
    const target = event.currentTarget;
    setScrolled(target.scrollTop > 2); // Add small threshold for better UX
  };

  const {loading, result: call} = useCall({
    entity: traceRootCall.project_id.split('/')[0],
    project: traceRootCall.project_id.split('/')[1],
    callId: traceRootCall.id,
  });

  const input = useMemo(() => {
    const rawInput = {...call?.traceCall?.inputs};
    if (rawInput && rawInput.self) {
      delete rawInput.self;
    }
    return rawInput;
  }, [call?.traceCall?.inputs]);

  const output = useMemo(() => {
    const rawOutput = call?.traceCall?.output;
    return rawOutput;
  }, [call?.traceCall?.output]);

  const handleClick = (e: React.MouseEvent) => {
    // Don't trigger trace selection when clicking expand buttons
    if ((e.target as HTMLElement).closest('button')) {
      e.stopPropagation();
      return;
    }
    onTraceSelect(traceRootCall.trace_id);
  };

  return (
    <ChatItem
      key={traceRootCall.id}
      $isSelected={traceRootCall.trace_id === selectedTraceId}
      onClick={handleClick}>
      <Section>
        <SectionHeader data-scrolled={isInputScrolled}>
          <Label>Input</Label>
          <ExpandButton
            variant="ghost"
            size="small"
            onClick={() => setIsInputExpanded(!isInputExpanded)}
            icon={isInputExpanded ? 'chevron-up' : 'chevron-down'}
          />
        </SectionHeader>
        <ContentWrapper>
          <Content
            ref={inputContentRef}
            $isExpanded={isInputExpanded}
            onScroll={e => handleScroll(e, setIsInputScrolled)}>
            {loading ? 'Loading...' : JSON.stringify(input, null, 2)}
          </Content>
        </ContentWrapper>
      </Section>
      <Section>
        <SectionHeader data-scrolled={isOutputScrolled}>
          <Label>Output</Label>
          <ExpandButton
            variant="ghost"
            size="small"
            onClick={() => setIsOutputExpanded(!isOutputExpanded)}
            icon={isOutputExpanded ? 'chevron-up' : 'chevron-down'}
          />
        </SectionHeader>
        <ContentWrapper>
          <Content
            ref={outputContentRef}
            $isExpanded={isOutputExpanded}
            onScroll={e => handleScroll(e, setIsOutputScrolled)}>
            {loading ? 'Loading...' : JSON.stringify(output, null, 2)}
          </Content>
        </ContentWrapper>
      </Section>
    </ChatItem>
  );
}
