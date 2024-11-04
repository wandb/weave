import Box from '@mui/material/Box';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React from 'react';

import {PlaygroundState, PlaygroundResponseFormats} from '../types';
import {FunctionEditor} from './FunctionEditor';
import {PlaygroundSlider} from './PlaygroundSlider';
import {ResponseFormatEditor} from './ResponseFormatEditor';
import {StopSequenceEditor} from './StopSequenceEditor';

export type PlaygroundSettingsProps = {
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: (
    idx: number,
    key: keyof PlaygroundState,
    value:
      | PlaygroundState[keyof PlaygroundState]
      | React.SetStateAction<Array<{name: string; [key: string]: any}>>
      | React.SetStateAction<PlaygroundResponseFormats>
      | React.SetStateAction<number>
      | React.SetStateAction<string[]>
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
            <Box sx={{display: 'flex', flexDirection: 'column', gap: 2, mt: 2}}>
              <FunctionEditor
                functions={playgroundState.functions}
                setFunctions={value =>
                  setPlaygroundStateField(idx, 'functions', value)
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

              <PlaygroundSlider
                min={1}
                max={100}
                step={1}
                setValue={value =>
                  setPlaygroundStateField(idx, 'nTimes', value)
                }
                label="n times to run"
                value={playgroundState.nTimes}
              />
            </Box>
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Box>
  );
};
