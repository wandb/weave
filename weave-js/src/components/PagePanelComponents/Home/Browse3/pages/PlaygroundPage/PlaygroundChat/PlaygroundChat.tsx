import {Box, CircularProgress, Divider} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import React, {SetStateAction, useState} from 'react';

import {PlaygroundState, PlaygroundStateKey} from '../types';
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
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [isLoading, setIsLoading] = useState(false);

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
                  left:
                    idx === 0
                      ? '8px'
                      : `calc(${(idx * 100) / playgroundStates.length}% + 8px)`,
                  right:
                    idx === playgroundStates.length - 1 ? '8px' : undefined,
                  width:
                    idx === playgroundStates.length - 1
                      ? undefined
                      : `calc(${100 / playgroundStates.length}% - 16px)`,
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
            </Box>
          </React.Fragment>
        ))}
      </Box>
    </Box>
  );
};
