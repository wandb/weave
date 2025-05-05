import {toast} from '@wandb/weave/common/components/elements/Toast';

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

type UseSaveModelConfigurationArgs = {
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  playgroundStates: PlaygroundState[];
  settingsTab: number;
  projectId: string;
  closeDialog: () => void;
  refetchSavedModels: () => void;
};

export const useSaveModelConfiguration = ({
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
