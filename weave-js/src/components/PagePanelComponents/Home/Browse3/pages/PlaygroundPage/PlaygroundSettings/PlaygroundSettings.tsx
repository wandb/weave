import Box from '@mui/material/Box';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {Switch} from '@wandb/weave/components';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React, {SetStateAction} from 'react';

import {PlaygroundState, PlaygroundStateKey} from '../types';
import {FunctionEditor} from './FunctionEditor';
import {PlaygroundSlider} from './PlaygroundSlider';
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
        width: '320px',
        overflowY: 'scroll',
        flexShrink: 0,
      }}>
      <Tabs.Root value={settingsTab.toString()}>
        <Tabs.List>
          {playgroundStates.map((state, idx) => (
            <Tabs.Trigger
              key={idx}
              value={idx.toString()}
              onClick={() => setSettingsTab(idx)}
              className="max-w-[120px]">
              {playgroundStates.length > 1 && <Tag label={`${idx + 1}`} />}
              <span className="truncate">{state.model}</span>
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
              <Box
                sx={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}>
                <label
                  className="cursor-pointer"
                  htmlFor="trackWithWeaveSwitch">
                  Track this LLM call with Weave
                </label>
                <Switch.Root
                  id="trackWithWeaveSwitch"
                  size="small"
                  checked={playgroundStates[idx].trackLLMCall}
                  onCheckedChange={() =>
                    setPlaygroundStateField(
                      idx,
                      'trackLLMCall',
                      !playgroundStates[idx].trackLLMCall
                    )
                  }>
                  <Switch.Thumb
                    size="small"
                    checked={playgroundStates[idx].trackLLMCall}
                  />
                </Switch.Root>
              </Box>
            </Box>
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Box>
  );
};
