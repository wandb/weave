import {Box, TextField, Tooltip} from '@mui/material';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {Button, Switch} from '@wandb/weave/components';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React, {useEffect, useState} from 'react';

import {SetPlaygroundStateFieldFunctionType} from '../PlaygroundChat/useChatFunctions';
import {
  JSON_PLAYGROUND_MODEL_PARAMS_KEYS,
  PLAYGROUND_MODEL_PARAMS_KEYS,
  PlaygroundState,
} from '../types';
import {useSaveModelConfiguration} from '../useSaveModelConfiguration';
import {FunctionEditor} from './FunctionEditor';
import {PlaygroundSlider} from './PlaygroundSlider';
import {ResponseFormatEditor} from './ResponseFormatEditor';
import {StopSequenceEditor} from './StopSequenceEditor';

export type PlaygroundSettingsProps = {
  playgroundStates: PlaygroundState[];
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  settingsTab: number;
  setSettingsTab: (tab: number | null) => void;
  projectId: string;
  refetchSavedModels: () => void;
};

export const PlaygroundSettings: React.FC<PlaygroundSettingsProps> = ({
  playgroundStates,
  setPlaygroundStateField,
  settingsTab,
  setSettingsTab,
  projectId,
  refetchSavedModels,
}) => {
  const [currentModelName, setCurrentModelName] = useState('');

  useEffect(() => {
    const objectId = playgroundStates[settingsTab]?.savedModel?.objectId;
    if (objectId != null) {
      setCurrentModelName(objectId);
    }
  }, [playgroundStates, settingsTab]);

  const {saveModelConfiguration} = useSaveModelConfiguration({
    setPlaygroundStateField,
    playgroundStates,
    settingsTab,
    projectId,
    refetchSavedModels,
  });

  const isUpdatingPublishedModel =
    playgroundStates[settingsTab]?.savedModel?.llmModelId;

  const areSettingsEqual = arePlaygroundSettingsEqual(
    currentModelName,
    playgroundStates[settingsTab]
  );

  return (
    <Box
      sx={{
        padding: '0 0 8px',
        height: '100%',
        borderLeft: `1px solid ${MOON_250}`,
        display: 'flex',
        flexDirection: 'column',
        width: '320px',
        flexShrink: 0,
        position: 'relative',
      }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          justifyContent: 'space-between',
          borderBottom: `1px solid ${MOON_250}`,
          padding: '8px 16px',
        }}>
        {/* Header */}
        <Box sx={{display: 'flex', alignItems: 'center', gap: '8px'}}>
          <Tag label={`${settingsTab + 1}`} />
          <Tooltip title={playgroundStates[settingsTab].model}>
            <Box
              sx={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontSize: '16px',
                fontWeight: '600',
              }}>
              {playgroundStates[settingsTab].model}
            </Box>
          </Tooltip>
        </Box>
        <Button
          tooltip={'Close settings drawer'}
          variant="ghost"
          size="medium"
          icon="close"
          onClick={() => {
            setSettingsTab(null);
          }}
        />
      </Box>
      <Box sx={{padding: '0 16px', overflowY: 'scroll', height: '100%'}}>
        <Tabs.Root value={settingsTab.toString()}>
          {playgroundStates.map((playgroundState, idx) => (
            <Tabs.Content key={idx} value={idx.toString()}>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  my: 2,
                }}>
                {/* Model Name Input */}
                <Box
                  sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    width: '100%',
                  }}>
                  <span style={{fontSize: '14px'}}>Model Name</span>
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      border: `1px solid ${MOON_250}`,
                      borderRadius: '4px',
                      width: '100%',
                    }}>
                    <TextField
                      value={currentModelName}
                      onChange={e => setCurrentModelName(e.target.value)}
                      placeholder="Enter model name..."
                      fullWidth
                      variant="standard"
                      sx={{
                        fontFamily: 'Source Sans Pro',
                        '& .MuiInputBase-root': {
                          border: 'none',
                          '&:before, &:after': {
                            borderBottom: 'none',
                          },
                          '&:hover:not(.Mui-disabled):before': {
                            borderBottom: 'none',
                          },
                        },
                        '& .MuiInputBase-input': {
                          padding: '8px',
                          fontFamily: 'Source Sans Pro',
                        },
                      }}
                    />
                  </Box>
                </Box>

                {/* Parameters */}
                <Box sx={{display: 'flex', flexDirection: 'column'}}>
                  <div className="font-[Source Sans Pro] mb-[-16px] text-sm font-semibold text-moon-500">
                    PARAMETERS
                  </div>
                </Box>

                {/* Response Format Editor */}
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
                  setValue={value =>
                    setPlaygroundStateField(idx, 'topP', value)
                  }
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

      <Box
        sx={{
          p: 2,
          borderTop: `1px solid ${MOON_250}`,
          backgroundColor: 'white',
        }}>
        <Button
          variant="primary"
          onClick={() => saveModelConfiguration(currentModelName)}
          className="w-full"
          disabled={
            playgroundStates.length === 0 ||
            !currentModelName.trim() ||
            areSettingsEqual
          }>
          {isUpdatingPublishedModel ? 'Update model' : 'Publish model'}
        </Button>
      </Box>
    </Box>
  );
};

// Compares saved model default params with current params
const arePlaygroundSettingsEqual = (
  currentModelName: string,
  currentPlaygroundState: PlaygroundState | undefined
): boolean => {
  const savedParams = currentPlaygroundState?.savedModel?.savedModelParams;
  if (
    !currentPlaygroundState ||
    !savedParams ||
    !currentPlaygroundState.savedModel?.llmModelId
  ) {
    return false; // Not equal if essential parts are missing
  }

  // First, check if the user is updating the objectId
  if (currentModelName !== currentPlaygroundState.savedModel.objectId) {
    return false;
  }

  for (const key of PLAYGROUND_MODEL_PARAMS_KEYS) {
    if (key === 'messagesTemplate') {
      const messagesTemplate = savedParams.messagesTemplate;
      const messages = currentPlaygroundState.traceCall?.inputs?.messages;
      if (JSON.stringify(messagesTemplate) !== JSON.stringify(messages)) {
        return false;
      }
      continue;
    }

    const currentValue = currentPlaygroundState[key];
    const savedValue = savedParams[key];

    if (JSON_PLAYGROUND_MODEL_PARAMS_KEYS.includes(key)) {
      const currentValueObject = currentValue ?? {};
      const savedValueObject = savedValue ?? {};
      if (
        JSON.stringify(currentValueObject) !== JSON.stringify(savedValueObject)
      ) {
        return false;
      }
    } else {
      // For other primitive types, direct comparison
      if (currentValue !== savedValue) {
        return false;
      }
    }
  }

  return true; // All compared keys are equal
};
