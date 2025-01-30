import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {Switch} from '@wandb/weave/components';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React from 'react';

import {SetPlaygroundStateFieldFunctionType} from '../PlaygroundChat/useChatFunctions';
import {PlaygroundState} from '../types';
import {FunctionEditor} from './FunctionEditor';
import {PlaygroundSlider} from './PlaygroundSlider';
import {ResponseFormatEditor} from './ResponseFormatEditor';
import {StopSequenceEditor} from './StopSequenceEditor';

export type PlaygroundSettingsProps = {
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
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
        padding: '0px 16px 8px 16px',
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
              <Tooltip title={state.model}>
                <span className="truncate">{state.model}</span>
              </Tooltip>
            </Tabs.Trigger>
          ))}
        </Tabs.List>
        {playgroundStates.map((playgroundState, idx) => (
          <Tabs.Content key={idx} value={idx.toString()}>
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                mt: 2,
              }}>
              <ResponseFormatEditor
                responseFormat={playgroundState.responseFormat}
                setResponseFormat={value =>
                  setPlaygroundStateField(idx, 'responseFormat', value)
                }
              />
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

              <StopSequenceEditor
                stopSequences={playgroundState.stopSequences}
                setStopSequences={value =>
                  setPlaygroundStateField(idx, 'stopSequences', value)
                }
              />

              {/* TODO: N times to run is not supported for all models */}
              {/* TODO: rerun in backend if this is not supported */}
              <PlaygroundSlider
                min={1}
                max={100}
                step={1}
                setValue={value =>
                  setPlaygroundStateField(idx, 'nTimes', value)
                }
                label="Number of trials"
                value={playgroundState.nTimes}
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
                }}>
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
                <label
                  className="ml-[8px] cursor-pointer text-[14px]"
                  htmlFor="trackWithWeaveSwitch">
                  Track this LLM call with Weave
                </label>
              </Box>
            </Box>
          </Tabs.Content>
        ))}
      </Tabs.Root>
    </Box>
  );
};
