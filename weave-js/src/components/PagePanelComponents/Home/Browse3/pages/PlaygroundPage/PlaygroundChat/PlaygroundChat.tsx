import {Box, CircularProgress, Divider} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {SetStateAction, useState} from 'react';

import {PlaygroundState, PlaygroundStateKey} from '../types';
import {PlaygroundChatInput} from './PlaygroundChatInput';
import {PlaygroundChatTopBar} from './PlaygroundChatTopBar';

export type PlaygroundChatProps = {
  entity: string;
  project: string;
  setPlaygroundStates: (states: PlaygroundState[]) => void;
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    index: number,
    field: PlaygroundStateKey,
    value: SetStateAction<PlaygroundState[PlaygroundStateKey]>
  ) => void;
  setSettingsTab: (callIndex: number | null) => void;
  settingsTab: number | null;
};

export const PlaygroundChat = ({
  entity,
  project,
  setPlaygroundStates,
  playgroundStates,
  setPlaygroundStateField,
  setSettingsTab,
  settingsTab,
}: PlaygroundChatProps) => {
  const [chatText, setChatText] = useState('');
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [isLoading, setIsLoading] = useState(false);
  const chatPercentWidth = 100 / playgroundStates.length;

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}>
      <Box
        sx={{
          width: '100%',
          height: '100%',
          maxHeight: 'calc(100% - 130px)',
          display: 'flex',
          position: 'relative',
        }}>
        {isLoading && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(255, 255, 255, 0.7)',
              zIndex: 100,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
            <CircularProgress />
          </Box>
        )}
        {playgroundStates.map((state, idx) => (
          <React.Fragment key={idx}>
            {idx > 0 && (
              <Divider
                orientation="vertical"
                flexItem
                sx={{
                  height: '100%',
                  borderRight: `1px solid ${MOON_200}`,
                }}
              />
            )}
            <Box
              sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
              }}>
              <Box
                sx={{
                  position: 'absolute',
                  top: '8px',
                  left: `calc(${idx * chatPercentWidth}% + 8px)`,
                  width: `calc(${chatPercentWidth}% - 16px)`,
                  zIndex: 10,
                }}>
                <PlaygroundChatTopBar
                  idx={idx}
                  settingsTab={settingsTab}
                  setSettingsTab={setSettingsTab}
                  setPlaygroundStateField={setPlaygroundStateField}
                  setPlaygroundStates={setPlaygroundStates}
                  playgroundStates={playgroundStates}
                  entity={entity}
                  project={project}
                />
              </Box>
              <Box
                sx={{
                  width: '100%',
                  height: '100%',
                  overflow: 'scroll',
                  paddingTop: '48px', // Height of the top bar
                  paddingX: '16px',
                }}>
                <Tailwind>
                  <div className="mx-auto h-full min-w-[400px] max-w-[800px] pb-8">
                    Chat
                  </div>
                </Tailwind>
              </Box>
            </Box>
          </React.Fragment>
        ))}
      </Box>
      <PlaygroundChatInput
        chatText={chatText}
        setChatText={setChatText}
        isLoading={isLoading}
        onSend={() => {}}
        onAdd={() => {}}
      />
    </Box>
  );
};
