import {TextField} from '@mui/material';
import {Button, Switch} from '@wandb/weave/components';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import {Tooltip} from '@wandb/weave/components/Tooltip';
import React, {useEffect, useState} from 'react';

import {SetPlaygroundStateFieldFunctionType} from '../PlaygroundChat/useChatFunctions';
import {PLAYGROUND_MODEL_PARAMS_KEYS, PlaygroundState} from '../types';
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
    <div className="relative flex h-full w-[320px] shrink-0 flex-col border-l border-moon-250 pb-4">
      <div className="flex items-center justify-between gap-8 border-b border-moon-250 px-16 py-8">
        {/* Header */}
        <div className="flex items-center gap-8">
          <Tag label={`${settingsTab + 1}`} />
          <Tooltip
            content={playgroundStates[settingsTab].model}
            trigger={
              <div className="overflow-hidden text-ellipsis whitespace-nowrap text-base font-semibold">
                {playgroundStates[settingsTab].model}
              </div>
            }
          />
        </div>
        <Button
          tooltip={'Close settings drawer'}
          variant="ghost"
          size="medium"
          icon="close"
          onClick={() => {
            setSettingsTab(null);
          }}
        />
      </div>
      <div className="h-full overflow-y-scroll px-16">
        <Tabs.Root value={settingsTab.toString()}>
          {playgroundStates.map((playgroundState, idx) => (
            <Tabs.Content key={idx} value={idx.toString()}>
              <div className="my-8 flex flex-col gap-16">
                {/* Model Name Input */}
                <div className="flex w-full flex-col gap-2">
                  <span className="text-sm">Model Name</span>
                  <div className="flex w-full flex-col rounded-md border border-moon-250">
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
                  </div>
                </div>

                {/* Parameters */}
                <div className="font-[Source Sans Pro] mb-[-16px] text-sm font-semibold text-moon-500">
                  PARAMETERS
                </div>

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

                <div className="flex w-full items-center">
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
                </div>
              </div>
            </Tabs.Content>
          ))}
        </Tabs.Root>
      </div>

      <div className="border-t border-moon-250 bg-white p-16">
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
      </div>
    </div>
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

  // Check each key in the saved params for equality
  for (const key of PLAYGROUND_MODEL_PARAMS_KEYS) {
    // messagesTemplate is a special case, because its stored in the trace call state
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

    // We compare the JSON strings of the current and saved values, since some values are not primitive types
    if (JSON.stringify(currentValue) !== JSON.stringify(savedValue)) {
      return false;
    }
  }

  // All compared keys are equal
  return true;
};
