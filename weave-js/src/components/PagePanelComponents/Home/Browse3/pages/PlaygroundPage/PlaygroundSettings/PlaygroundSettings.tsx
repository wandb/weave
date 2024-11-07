import {Switch} from '@mui/material';
import Box from '@mui/material/Box';
import {MOON_250, TEAL_500} from '@wandb/weave/common/css/color.styles';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React, {SetStateAction} from 'react';

import {PlaygroundState, PlaygroundStateKey} from '../types';
import {FunctionEditor} from './FunctionEditor';
import {PlaygroundSlider} from './PlaygroundSlider';
import {ResponseFormatEditor} from './ResponseFormatEditor';
import {StopSequenceEditor} from './StopSequenceEditor';

export type PlaygroundSettingsProps = {
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    index: number,
    field: PlaygroundStateKey,
    value: SetStateAction<PlaygroundState[PlaygroundStateKey]>
  ) => void;
  settingsTab: number;
  setSettingsTab: (tab: number) => void;
};

export const PlaygroundSettings: React.FC<PlaygroundSettingsProps> = ({
  playgroundStates,
  setPlaygroundStateField,
  settingsTab,
  setSettingsTab,
}) => {
  return (
    <Box
      sx={{
        padding: '16px',
        height: '100%',
        borderLeft: `1px solid ${MOON_250}`,
        display: 'flex',
        flexDirection: 'column',
        width: '400px',
        minWidth: '260px',
        overflowY: 'scroll',
      }}>
      <Tabs.Root value={settingsTab.toString()}>
        <Tabs.List>
          {playgroundStates.map((state, idx) => (
            <Tabs.Trigger
              key={idx}
              value={idx.toString()}
              onClick={() => setSettingsTab(idx)}>
              {playgroundStates.length > 1 && <Tag label={`${idx + 1}`} />}
              {state.model}
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {playgroundStates.map((playgroundState, idx) => (
          <Tabs.Content key={idx} value={idx.toString()}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
                mt: 2,
              }}>
              <FunctionEditor
                playgroundState={playgroundState}
                functions={playgroundState.functions}
                setFunctions={value =>
                  setPlaygroundStateField(
                    idx,
                    'functions',
                    value as Array<{name: string; [key: string]: any}>
                  )
                }
              />

              <ResponseFormatEditor
                responseFormat={playgroundState.responseFormat}
                setResponseFormat={value =>
                  setPlaygroundStateField(idx, 'responseFormat', value)
                }
              />

              <PlaygroundSlider
                min={0}
                max={2}
                step={0.01}
                setValue={value =>
                  setPlaygroundStateField(idx, 'temperature', value)
                }
                label="Temperature"
                value={playgroundState.temperature}
              />

              <PlaygroundSlider
                min={0}
                max={playgroundState.maxTokensLimit || 100}
                step={1}
                setValue={value =>
                  setPlaygroundStateField(idx, 'maxTokens', value)
                }
                label="Maximum tokens"
                value={playgroundState.maxTokens}
              />

              <StopSequenceEditor
                stopSequences={playgroundState.stopSequences}
                setStopSequences={value =>
                  setPlaygroundStateField(idx, 'stopSequences', value)
                }
              />

              <PlaygroundSlider
                min={0}
                max={1}
                step={0.01}
                setValue={value => setPlaygroundStateField(idx, 'topP', value)}
                label="Top P"
                value={playgroundState.topP}
              />

              <PlaygroundSlider
                min={0}
                max={1}
                step={0.01}
                setValue={value =>
                  setPlaygroundStateField(idx, 'frequencyPenalty', value)
                }
                label="Frequency penalty"
                value={playgroundState.frequencyPenalty}
              />

              <PlaygroundSlider
                min={0}
                max={1}
                step={0.01}
                setValue={value =>
                  setPlaygroundStateField(idx, 'presencePenalty', value)
                }
                label="Presence penalty"
                value={playgroundState.presencePenalty}
              />

              {/* TODO: Add this back in, N times to run is not supported for all models */}
              {/* Shawn said to run multiple requests if its not supported */}
              {/* <PlaygroundSlider
                min={1}
                max={100}
                step={1}
                setValue={value =>
                  setPlaygroundStateField(idx, 'nTimes', value)
                }
                label="n times to run"
                value={playgroundState.nTimes}
              /> */}

              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                <span>Track this LLM call with Weave</span>
                <Switch
                  checked={playgroundStates[idx].trackLLMCall}
                  onChange={() =>
                    setPlaygroundStateField(
                      idx,
                      'trackLLMCall',
                      !playgroundStates[idx].trackLLMCall
                    )
                  }
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: TEAL_500,
                      '&:hover': {
                        backgroundColor: `${TEAL_500}/[.5]`,
                      },
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      backgroundColor: TEAL_500,
                    },
                    '& .MuiSwitch-switchBase.Mui-checked:hover': {
                      backgroundColor: `${TEAL_500}/[.5]`,
                    },
                  }}
                />
              </Box>
            </Box>
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Box>
  );
};
