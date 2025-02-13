import {Box} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useState} from 'react';

import {CallChat} from '../../CallPage/CallChat';
import {TraceCallSchema} from '../../wfReactInterface/traceServerClientTypes';
import {PlaygroundContext} from '../PlaygroundContext';
import {PlaygroundMessageRole, PlaygroundState} from '../types';
import {PlaygroundCallStats} from './PlaygroundCallStats';
import {PlaygroundChatInput} from './PlaygroundChatInput';
import {PlaygroundChatMessages} from './PlaygroundChatMessages';
import {PlaygroundChatTopBar} from './PlaygroundChatTopBar';
import {useChatCompletionFunctions} from './useChatCompletionFunctions';
import {
  SetPlaygroundStateFieldFunctionType,
  useChatFunctions,
} from './useChatFunctions';

export type PlaygroundChatProps = {
  entity: string;
  project: string;
  setPlaygroundStates: (states: PlaygroundState[]) => void;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  setSettingsTab: (callIndex: number | null) => void;
  settingsTab: number | null;
  agentdome?: boolean;
};

export const PlaygroundChat: React.FC<PlaygroundChatProps> = ({
  playgroundStates,
  setPlaygroundStates,
  setPlaygroundStateField,
  entity,
  project,
  settingsTab,
  setSettingsTab,
  agentdome,
}) => {
  const [chatText, setChatText] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const {handleSend} = useChatCompletionFunctions(
    setPlaygroundStates,
    setIsLoading,
    playgroundStates,
    entity,
    project,
    setChatText
  );

  const {addMessage} = useChatFunctions(setPlaygroundStateField);

  const handleAddMessage = (role: PlaygroundMessageRole, text: string) => {
    for (let i = 0; i < playgroundStates.length; i++) {
      addMessage(i, {role, content: text});
    }
    setChatText('');
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
      }}>
      <Box
        sx={{
          display: agentdome ? 'grid' : 'flex',
          gridTemplateColumns: agentdome ? '1fr 1fr' : 'auto',
          gridTemplateRows: agentdome ? '0.8fr 1fr' : 'auto',
          gap: '8px',
          padding: '8px',
          height: '100%',
          width: '100%',
          overflow: 'hidden',
        }}>
        {playgroundStates.map((playgroundState, idx) => (
          <Box
            key={idx}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              height: '100%',
              width: '100%',
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: '4px',
              overflow: 'hidden',
              padding: agentdome ? '8px 16px' : '0px',
            }}>
            <PlaygroundChatTopBar
              idx={idx}
              settingsTab={settingsTab}
              setSettingsTab={setSettingsTab}
              setPlaygroundStateField={setPlaygroundStateField}
              entity={entity}
              project={project}
              playgroundStates={playgroundStates}
              setPlaygroundStates={setPlaygroundStates}
              agentdome={agentdome}
            />
            <PlaygroundChatMessages
              playgroundState={playgroundState}
              setPlaygroundStateField={setPlaygroundStateField}
              idx={idx}
              entity={entity}
              project={project}
              handleSend={handleSend}
            />
            <PlaygroundChatInput
              playgroundState={playgroundState}
              setPlaygroundStateField={setPlaygroundStateField}
              idx={idx}
              entity={entity}
              project={project}
              chatText={chatText}
              setChatText={setChatText}
              isLoading={isLoading}
              handleSend={handleSend}
              handleAddMessage={handleAddMessage}
              settingsTab={settingsTab}
            />
          </Box>
        ))}
      </Box>
    </Box>
  );
};
