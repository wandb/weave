import React, { useMemo } from 'react';
import styled from 'styled-components';

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
  background ${props => (props.$isSelected ? '#EFF6FF' : 'white')} ;
  cursor: pointer;
  transition: all 0.15s ease;
  overflow: hidden;

  &:hover {
    border-color: ${props => (props.$isSelected ? '#3B82F6' : '#94A3B8')};
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
  const {loading, result: call} = useCall({
    entity: traceRootCall.project_id.split('/')[0],
    project: traceRootCall.project_id.split('/')[1],
    callId: traceRootCall.id,
  });

  const input = useMemo(() => {
    const rawInput = {...call?.traceCall?.inputs};
    if (rawInput && rawInput['self']) {
      delete rawInput['self'];
    }
    return rawInput;
    // return processInput(rawInput);
  }, [call?.traceCall?.inputs])

  const output = useMemo(() => {
    const rawOutput = call?.traceCall?.output
    return rawOutput;
    // return processOutput(rawOutput);
  }, [call?.traceCall?.output])

  return (
    <ChatItem
      key={traceRootCall.id}
      $isSelected={traceRootCall.trace_id === selectedTraceId}
      onClick={() => onTraceSelect(traceRootCall.trace_id)}>
      <InputSection>
        <Label>Input</Label>
        <Content>
          {loading ? (
            'Loading...'
          ) : (
            JSON.stringify(input, null, 2)
          )}
        </Content>
      </InputSection>
      <OutputSection>
        <Label>Output</Label>
        <Content>
          {loading ? (
            'Loading...'
          ) : (
            JSON.stringify(output, null, 2)
          )}
        </Content>
      </OutputSection>
    </ChatItem>
  );
}
