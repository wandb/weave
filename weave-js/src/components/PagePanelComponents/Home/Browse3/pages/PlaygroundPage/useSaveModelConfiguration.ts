import {toast} from '@wandb/weave/common/components/elements/Toast';

import {
  LlmStructuredCompletionModel,
  LlmStructuredCompletionModelDefaultParams,
  LlmStructuredCompletionModelDefaultParamsSchema,
  Message,
  ResponseFormatSchema,
} from '../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {useCreateBuiltinObjectInstance} from '../wfReactInterface/objectClassQuery';
import {LLMMaxTokensKey} from './llmMaxTokens';
import {
  SetPlaygroundStateFieldFunctionType,
  TraceCallOutput,
} from './PlaygroundChat/useChatFunctions';
import {
  OptionalSavedPlaygroundModelParams,
  PlaygroundResponseFormats,
  PlaygroundState,
} from './types';

type UseSaveModelConfigurationArgs = {
  setPlaygroundStateField: SetPlaygroundStateFieldFunctionType;
  playgroundStates: PlaygroundState[];
  settingsTab: number;
  projectId: string;
  refetchSavedModels: () => void;
};

export const useSaveModelConfiguration = ({
  setPlaygroundStateField,
  playgroundStates,
  settingsTab,
  projectId,
  refetchSavedModels,
}: UseSaveModelConfigurationArgs) => {
  const createLLMStructuredCompletionModel = useCreateBuiltinObjectInstance(
    'LLMStructuredCompletionModel'
  );

  const saveModelConfiguration = async (modelName: string) => {
    const finalModelName = modelName.trim();
    // This should never happen(button is disabled), but just in case
    if (!finalModelName) {
      toast('Model name cannot be empty.', {type: 'error'});
      return;
    }

    const state = playgroundStates[settingsTab];
    if (!state) {
      toast('Cannot find current playground state.', {type: 'error'});
      return;
    }

    const defaultParams: LlmStructuredCompletionModel['default_params'] = {
      temperature: state.temperature,
      top_p: state.topP,
      max_tokens: state.maxTokens,
      presence_penalty: state.presencePenalty,
      frequency_penalty: state.frequencyPenalty,
      stop: state.stopSequences ?? [],
      response_format:
        state.responseFormat === PlaygroundResponseFormats.JsonObject
          ? ResponseFormatSchema.parse('json')
          : state.responseFormat === PlaygroundResponseFormats.Text
          ? ResponseFormatSchema.parse('text')
          : undefined,
      functions: state.functions,
      n_times: state.nTimes,
      messages_template: [],
    };

    const addMessageToTemplate = (message: Message) => {
      defaultParams.messages_template.push({
        content: message.content,
        function_call: message.function_call ?? null,
        name: message.name ?? null,
        role: message.role,
        tool_call_id: message.tool_call_id ?? null,
      });
    };

    if (state.traceCall?.inputs?.messages) {
      state.traceCall.inputs.messages.forEach(addMessageToTemplate);
    }

    const choice = (state.traceCall?.output as TraceCallOutput)?.choices?.[
      state.selectedChoiceIndex ?? 0
    ];
    if (choice) {
      addMessageToTemplate(choice.message);
    }

    // Validate the default parameters
    const validatedParams =
      LlmStructuredCompletionModelDefaultParamsSchema.safeParse(defaultParams);
    if (!validatedParams.success) {
      console.error('Parameter validation failed:', validatedParams.error);
      toast(`Invalid parameters: ${validatedParams.error.message}`, {
        type: 'error',
      });
      return;
    }

    // Get the base model id (if resaving llmModelId, otherwise use the current model)
    const baseModelId = state.savedModel?.llmModelId
      ? state.savedModel.llmModelId
      : state.model;

    // Create payload for the new model
    const modelToSave: Omit<LlmStructuredCompletionModel, 'ref'> & {
      name: string;
    } = {
      name: finalModelName,
      llm_model_id: baseModelId,
      default_params: validatedParams.data,
    };

    // Save the new model
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

      // Update state so LLM dropdown shows the new model
      setPlaygroundStateField(settingsTab, 'savedModel', {
        name: baseModelId,
        savedModelParams: convertDefaultParamsToOptionalPlaygroundModelParams(
          validatedParams.data
        ),
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

// Helper function to convert backend saved model parameters to playground state format
export const convertDefaultParamsToOptionalPlaygroundModelParams = (
  defaultParams: LlmStructuredCompletionModelDefaultParams | null | undefined
): OptionalSavedPlaygroundModelParams => {
  if (!defaultParams) return {};

  // Helper function to convert null or undefined to undefined
  const nullToUndefined = (value: any) => {
    return value === null || value === undefined ? undefined : value;
  };

  // We want undefined instead of null for the default params
  return {
    temperature: nullToUndefined(defaultParams.temperature),
    topP: nullToUndefined(defaultParams.top_p),
    maxTokens: nullToUndefined(defaultParams.max_tokens),
    frequencyPenalty: nullToUndefined(defaultParams.frequency_penalty),
    presencePenalty: nullToUndefined(defaultParams.presence_penalty),
    nTimes: nullToUndefined(defaultParams.n_times) ?? 1,
    responseFormat: nullToUndefined(
      defaultParams.response_format as PlaygroundResponseFormats
    ),
    functions: nullToUndefined(defaultParams.functions),
    stopSequences: nullToUndefined(defaultParams.stop),
    messagesTemplate: nullToUndefined(defaultParams.messages_template),
  };
};
