import {Box} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {CallChat} from '../../CallPage/CallChat';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {PlaygroundContext} from '../PlaygroundContext';
import {PlaygroundMessageRole, PlaygroundState} from '../types';
import {PlaygroundCallStats} from './PlaygroundCallStats';
import {
  SetPlaygroundStateFieldFunctionType,
  useChatFunctions,
} from './useChatFunctions';

interface PlaygroundChatMessagesProps {
  playgroundState: PlaygroundState;
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  idx: number;
  entity: string;
  project: string;
  handleSend: (
    role: PlaygroundMessageRole,
    chatText: string,
    callIndex?: number,
    content?: string,
    toolCallId?: string
  ) => Promise<void>;
}

export const PlaygroundChatMessages: React.FC<PlaygroundChatMessagesProps> = ({
  playgroundState,
  setPlaygroundStateField,
  idx,
  entity,
  project,
  handleSend,
}) => {
  const {deleteMessage, editMessage, deleteChoice, editChoice, addMessage} =
    useChatFunctions(setPlaygroundStateField);

  const handleRetry = async (messageIndex: number, choiceIndex?: number) => {
    const messages = playgroundState.traceCall.inputs?.messages || [];
    if (messageIndex < messages.length) {
      const messageToRetry = messages[messageIndex];
      await handleSend(
        messageToRetry.role as PlaygroundMessageRole,
        messageToRetry.content || '',
        idx,
        messageToRetry.content,
        messageToRetry.tool_call_id
      );
    }
  };

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        overflow: 'auto',
        paddingX: '16px',
        flexGrow: 1,
      }}>
      <Tailwind>
        <div className="mx-auto mt-[32px] h-full min-w-[200px] max-w-[800px] pb-8">
          {playgroundState.traceCall && (
            <PlaygroundContext.Provider
              value={{
                isPlayground: true,
                deleteMessage: (messageIndex, responseIndexes) =>
                  deleteMessage(idx, messageIndex, responseIndexes),
                editMessage: (messageIndex, newMessage) =>
                  editMessage(idx, messageIndex, newMessage),
                deleteChoice: (messageIndex, choiceIndex) =>
                  deleteChoice(idx, choiceIndex),
                addMessage: newMessage => addMessage(idx, newMessage),
                editChoice: (choiceIndex, newChoice) =>
                  editChoice(idx, choiceIndex, newChoice),
                retry: handleRetry,
                sendMessage: (role, content, toolCallId) =>
                  handleSend(role, content, idx, content, toolCallId),
                setSelectedChoiceIndex: (choiceIndex: number) =>
                  setPlaygroundStateField(
                    idx,
                    'selectedChoiceIndex',
                    choiceIndex
                  ),
              }}>
              <CallChat call={playgroundState.traceCall as TraceCallSchema} />
            </PlaygroundContext.Provider>
          )}
        </div>
        {playgroundState.traceCall.summary && (
          <Box sx={{padding: '8px 0'}}>
            <PlaygroundCallStats
              call={playgroundState.traceCall as TraceCallSchema}
            />
          </Box>
        )}
      </Tailwind>
    </Box>
  );
};
