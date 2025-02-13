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
}

export const PlaygroundChatMessages: React.FC<PlaygroundChatMessagesProps> = ({
  playgroundState,
  setPlaygroundStateField,
  idx,
  entity,
  project,
}) => {
  const {deleteMessage, editMessage, deleteChoice, editChoice, addMessage} =
    useChatFunctions(setPlaygroundStateField);

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
                retry: () => {}, // This will be handled by the parent
                sendMessage: () => {}, // This will be handled by the parent
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
