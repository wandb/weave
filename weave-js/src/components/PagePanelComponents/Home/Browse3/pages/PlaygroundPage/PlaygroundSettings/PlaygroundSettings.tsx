import {Box, Tooltip} from '@mui/material';
import {toast} from '@wandb/weave/common/components/elements/Toast';
import {MOON_250} from '@wandb/weave/common/css/color.styles';
import {Button, Switch} from '@wandb/weave/components';
import * as Tabs from '@wandb/weave/components/Tabs';
import {Tag} from '@wandb/weave/components/Tag';
import React, {useState} from 'react';

import {
  LlmStructuredCompletionModel,
  LlmStructuredCompletionModelDefaultParamsSchema,
  Message,
  ResponseFormatSchema,
} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {useCreateBuiltinObjectInstance} from '../../wfReactInterface/objectClassQuery';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {
  SetPlaygroundStateFieldFunctionType,
  TraceCallOutput,
} from '../PlaygroundChat/useChatFunctions';
import {PlaygroundResponseFormats, PlaygroundState} from '../types';
import {FunctionEditor} from './FunctionEditor';
import {PlaygroundSlider} from './PlaygroundSlider';
import {ResponseFormatEditor} from './ResponseFormatEditor';
import {SaveModelModal} from './SaveModelModal';
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
  const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);
  const [initialSaveName, setInitialSaveName] = useState('');

  const handleSaveClick = () => {
    const currentModelName = playgroundStates[settingsTab]?.model;
    setInitialSaveName(
      currentModelName
        ? `${currentModelName.replace('/', '-')}-saved`
        : 'saved-model'
    );
    setIsSaveDialogOpen(true);
  };

  const handleSaveDialogClose = () => {
    setIsSaveDialogOpen(false);
  };

  const {saveModelConfiguration} = useSaveModelConfiguration({
    setPlaygroundStateField,
    playgroundStates,
    settingsTab,
    projectId,
    closeDialog: handleSaveDialogClose,
    refetchSavedModels,
  });

  return (
    <Box
      sx={{
        padding: '0 0 8px',
        height: '100%',
        borderLeft: `1px solid ${MOON_250}`,
        display: 'flex',
        flexDirection: 'column',
        width: '320px',
        overflowY: 'scroll',
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
        <Box sx={{display: 'flex', alignItems: 'center', gap: '8px'}}>
          <Tag label={`${settingsTab + 1}`} />
          <Tooltip title={playgroundStates[settingsTab ?? 0]?.model ?? ''}>
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
      <Box sx={{padding: '0 16px'}}>
        <Tabs.Root value={settingsTab.toString()}>
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
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          p: 2,
          borderTop: `1px solid ${MOON_250}`,
          backgroundColor: 'white',
          zIndex: 1,
        }}>
        <Button
          variant="primary"
          onClick={handleSaveClick}
          className="w-full"
          disabled={playgroundStates.length === 0}>
          Publish Model
        </Button>
      </Box>

      <SaveModelModal
        isOpen={isSaveDialogOpen}
        onClose={handleSaveDialogClose}
        onSave={saveModelConfiguration}
        initialModelName={initialSaveName}
      />
    </Box>
  );
};

type UseSaveModelConfigurationArgs = {
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  playgroundStates: PlaygroundState[];
  settingsTab: number;
  projectId: string;
  closeDialog: () => void;
  refetchSavedModels: () => void;
};

const useSaveModelConfiguration = ({
  setPlaygroundStateField,
  playgroundStates,
  settingsTab,
  projectId,
  closeDialog,
  refetchSavedModels,
}: UseSaveModelConfigurationArgs) => {
  const createLLMStructuredCompletionModel = useCreateBuiltinObjectInstance(
    'LLMStructuredCompletionModel'
  );

  const saveModelConfiguration = async (modelName: string) => {
    const finalModelName = modelName.trim();
    if (!finalModelName) {
      toast('Model name cannot be empty.', {type: 'error'});
      return;
    }

    const currentState = playgroundStates[settingsTab];
    if (!currentState) {
      toast('Cannot find current playground state.', {type: 'error'});
      closeDialog();
      return;
    }

    const defaultParams: LlmStructuredCompletionModel['default_params'] = {
      temperature: currentState.temperature,
      top_p: currentState.topP,
      max_tokens: currentState.maxTokens,
      presence_penalty: currentState.presencePenalty,
      frequency_penalty: currentState.frequencyPenalty,
      stop: currentState.stopSequences ?? [],
      response_format:
        currentState.responseFormat === PlaygroundResponseFormats.JsonObject
          ? ResponseFormatSchema.parse('json')
          : currentState.responseFormat === PlaygroundResponseFormats.Text
          ? ResponseFormatSchema.parse('text')
          : // : currentState.responseFormat === PlaygroundResponseFormats.JsonSchema
            // ? ResponseFormatSchema.parse('jsonschema')
            undefined,
      functions: currentState.functions,
      n_times: currentState.nTimes,
      messages_template: [],
    };

    if (currentState.traceCall?.inputs?.messages) {
      defaultParams.messages_template.push(
        ...currentState.traceCall.inputs.messages.map((message: Message) => ({
          content: message.content,
          function_call: message.function_call ?? null,
          name: message.name ?? null,
          role: message.role,
          tool_call_id: message.tool_call_id ?? null,
        }))
      );
    }
    if (
      currentState.traceCall?.output &&
      (currentState.traceCall.output as TraceCallOutput)?.choices
    ) {
      const choice = (currentState.traceCall.output as TraceCallOutput)
        ?.choices?.[currentState.selectedChoiceIndex ?? 0];
      if (choice) {
        defaultParams.messages_template.push({
          content: choice?.message.content,
          function_call: choice?.message.function_call ?? null,
          name: choice?.message.name ?? null,
          role: choice?.message.role,
          tool_call_id: choice?.message.tool_call_id ?? null,
        });
      }
    }

    const validatedParams =
      LlmStructuredCompletionModelDefaultParamsSchema.safeParse(defaultParams);
    if (!validatedParams.success) {
      console.error('Parameter validation failed:', validatedParams.error);
      toast(`Invalid parameters: ${validatedParams.error.message}`, {
        type: 'error',
      });
      return;
    }

    const baseModelId = currentState.savedModel?.name
      ? currentState.savedModel.name
      : currentState.model;

    const modelToSave: Omit<LlmStructuredCompletionModel, 'ref'> & {
      name: string;
    } = {
      name: finalModelName,
      llm_model_id: baseModelId,
      default_params: validatedParams.data,
    };

    closeDialog();

    try {
      await createLLMStructuredCompletionModel({
        obj: {
          project_id: projectId,
          object_id: finalModelName,
          val: modelToSave,
        },
      });
      toast(`Model "${finalModelName}" saved successfully!`, {
        type: 'success',
      });

      refetchSavedModels();

      setPlaygroundStateField(settingsTab, 'savedModel', {
        name: baseModelId,
        savedModelParams: validatedParams.data,
      });

      setPlaygroundStateField(
        settingsTab,
        'model',
        finalModelName as LLMMaxTokensKey
      );
    } catch (error) {
      console.error('Failed to save model:', error);
      toast(`Failed to save model: ${error}`, {
        type: 'error',
      });
    }
  };

  return {saveModelConfiguration};
};
