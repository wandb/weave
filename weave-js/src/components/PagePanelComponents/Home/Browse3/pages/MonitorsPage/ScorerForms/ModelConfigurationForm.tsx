import {Box, Typography} from '@mui/material';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {validateDatasetName} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/datasets/datasetNameValidation';
import {
  FieldName,
  typographyStyle,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/FormComponents';
import {
  useCreateBuiltinObjectInstance,
  useLeafObjectInstances,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/objectClassQuery';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from 'react';

import {LLMDropdownLoaded} from '../../PlaygroundPage/PlaygroundChat/LLMDropdown';
import {ResponseFormatSelect} from '../../PlaygroundPage/PlaygroundSettings/ResponseFormatEditor';
import {PlaygroundResponseFormats} from '../../PlaygroundPage/types';
import {
  LlmStructuredCompletionModel,
  LlmStructuredCompletionModelDefaultParams,
  ResponseFormat,
} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';

export interface ModelConfigurationFormRef {
  saveModel: () => Promise<string | undefined>;
  isValid: boolean;
}

export interface ModelConfigurationFormProps {
  initialModelRef?: string;
  onValidationChange?: (isValid: boolean) => void;
  onModelChange?: (model: LlmStructuredCompletionModel | undefined) => void;
}

/**
 * Reusable component for configuring LLM models with structured completion capabilities.
 * Extracted from LLMAsAJudgeScorerForm to be used in various contexts.
 */
export const ModelConfigurationForm = forwardRef<
  ModelConfigurationFormRef,
  ModelConfigurationFormProps
>(({initialModelRef, onValidationChange, onModelChange}, ref) => {
  const [model, setModel] = useState<LlmStructuredCompletionModel | undefined>(
    undefined
  );

  const [modelError, setModelError] = useState<string | null>(null);

  const [modelName, setModelName] = useState<string | undefined>();

  const [systemPrompt, setSystemPrompt] = useState<string | undefined>();

  const [responseFormat, setResponseFormat] = useState<
    ResponseFormat | undefined
  >();

  const {projectId, entity, project} = useEntityProject();

  const {result: savedModelRes} = useLeafObjectInstances(
    'LLMStructuredCompletionModel',
    {
      project_id: projectId,
    }
  );

  const savedModels: LlmStructuredCompletionModel[] = useMemo(
    () =>
      savedModelRes?.map(model => {
        const savedModel = model.val as LlmStructuredCompletionModel;
        // Creating a ref so we can track the version index
        savedModel.ref = {
          entity,
          project,
          name: savedModel.name || '',
          _digest: model.digest,
          // We presume current _extra is empty
          _extra: [`${model.version_index}`],
        };
        return savedModel;
      }) || [],
    [savedModelRes, entity, project]
  );

  // Load initial model if provided
  useEffect(() => {
    if (!savedModels || !initialModelRef) {
      return;
    }
    const currentModel = savedModels.find(
      model =>
        `weave:///${projectId}/object/${model.name}:${model.ref?._digest}` ===
        initialModelRef
    );
    if (currentModel) {
      setModel(currentModel);
      onValidationChange?.(true);
      if (currentModel.default_params) {
        const systemPrompt = getSystemPrompt(currentModel.default_params);
        setSystemPrompt(systemPrompt);
      }
    }
  }, [
    savedModels,
    entity,
    project,
    projectId,
    initialModelRef,
    onValidationChange,
  ]);

  const selectedModel = useMemo(() => {
    if (model) {
      if (model.ref) {
        // This is a saved model
        return `${model.name}:v${model.ref?._extra?.[0]}`;
      }
      return model.llm_model_id;
    }
    return undefined;
  }, [model]);

  const validateModel = useCallback(() => {
    if (!model) {
      setModelError('A model is required.');
      return false;
    } else {
      if (!modelName) {
        setModelError('A model name is required.');
        return false;
      }
      if (!responseFormat) {
        setModelError('A model response format is required.');
        return false;
      }
    }
    setModelError(null);
    return true;
  }, [model, modelName, responseFormat]);

  const createLLMStructuredCompletionModel = useCreateBuiltinObjectInstance(
    'LLMStructuredCompletionModel'
  );

  const saveModel = useCallback(async (): Promise<string | undefined> => {
    if (!model) {
      return undefined;
    }

    const modelToSave: LlmStructuredCompletionModel = {
      llm_model_id: model.llm_model_id,
      name: modelName,
      default_params: {
        ...model.default_params,
        messages_template: systemPrompt
          ? [{role: 'system', content: systemPrompt}]
          : undefined,
        response_format: responseFormat,
      },
    };

    try {
      const response = await createLLMStructuredCompletionModel({
        obj: {
          project_id: projectId,
          object_id: modelToSave.name as string,
          val: modelToSave,
        },
      });
      console.log('saveModel', 'post response', response);
      return `weave:///${projectId}/object/${modelToSave.name}:${response.digest}`;
    } catch (error) {
      console.error('Failed to save model:', error);
    }
    return undefined;
  }, [
    projectId,
    model,
    modelName,
    systemPrompt,
    responseFormat,
    createLLMStructuredCompletionModel,
  ]);

  useImperativeHandle(ref, () => ({
    saveModel,
    isValid: validateModel(),
  }));

  const onModelNameChange = useCallback(
    value => {
      setModelName(value);
      const validationResult = validateDatasetName(value);
      setModelError(validationResult.error);
      onValidationChange?.(
        !validationResult.error && !!value && !!systemPrompt && !!responseFormat
      );
    },
    [
      systemPrompt,
      responseFormat,
      setModelName,
      setModelError,
      onValidationChange,
    ]
  );

  const onSystemPromptChange = useCallback(
    value => {
      setSystemPrompt(value);
      onValidationChange?.(!!value && !!modelName && !!responseFormat);
    },
    [modelName, responseFormat, onValidationChange]
  );

  const handleModelChange = useCallback(
    (newValue, maxTokens, savedModel) => {
      let newModel: LlmStructuredCompletionModel | undefined;

      if (savedModel && savedModels) {
        newModel = savedModels.find(
          model =>
            model.name === savedModel.objectId &&
            model.ref?._extra?.[0] === `${savedModel.versionIndex}`
        );
      } else {
        newModel = {
          llm_model_id: newValue,
          name: modelName || 'new-model',
          default_params: {
            max_tokens: maxTokens,
          },
          description: '',
          ref: undefined,
        };
      }
      setModel(newModel);
      onModelChange?.(newModel);
      // Clear error when model is selected
      setModelError(null);
      onValidationChange?.(!!modelName && !!systemPrompt);
    },
    [
      modelName,
      systemPrompt,
      savedModels,
      setModel,
      onModelChange,
      onValidationChange,
    ]
  );

  useMemo(() => {
    setModelName(model?.name || undefined);
    setSystemPrompt(
      model?.default_params && getSystemPrompt(model.default_params)
    );
    setResponseFormat(model?.default_params?.response_format || 'json_object');
  }, [model]);

  if (!model) {
    return (
      <Box>
        <FieldName name="Model" />
        <LLMDropdownLoaded
          className="w-full"
          value={selectedModel || ''}
          isTeamAdmin={false}
          direction={{horizontal: 'left'}}
          onChange={handleModelChange}
        />
        {modelError && (
          <Typography
            className="mt-1 text-sm"
            sx={{
              ...typographyStyle,
              color: 'error.main',
            }}>
            {modelError}
          </Typography>
        )}
      </Box>
    );
  }

  return (
    <>
      <Box>
        <FieldName name="Model" />
        <LLMDropdownLoaded
          className="w-full"
          value={selectedModel || ''}
          isTeamAdmin={false}
          direction={{horizontal: 'left'}}
          onChange={handleModelChange}
        />
        {modelError && (
          <Typography
            className="mt-1 text-sm"
            sx={{
              ...typographyStyle,
              color: 'error.main',
            }}>
            {modelError}
          </Typography>
        )}
      </Box>

      <Box className="flex flex-col gap-16 rounded-md bg-moon-100 p-16">
        <Typography
          sx={typographyStyle}
          className="text-sm font-semibold uppercase tracking-wide text-moon-500">
          Model settings
        </Typography>

        <Box>
          <FieldName name="LLM ID" />
          <Typography sx={{...typographyStyle, color: 'text.secondary'}}>
            {model.llm_model_id}
          </Typography>
        </Box>
        <Box>
          <FieldName name="Configuration name" />
          <TextField value={modelName} onChange={onModelNameChange} />
        </Box>
        <Box>
          <FieldName name="System prompt" />
          <TextArea
            value={systemPrompt}
            onChange={e => onSystemPromptChange(e.target.value)}
          />
        </Box>
        <Box>
          <FieldName name="Response format" />
          <ResponseFormatSelect
            responseFormat={
              (responseFormat || 'json_object') as PlaygroundResponseFormats
            }
            setResponseFormat={setResponseFormat}
          />
        </Box>
      </Box>
    </>
  );
});

/**
 * Helper function to extract system prompt from model default parameters
 */
function getSystemPrompt(
  modelDefaultParams: LlmStructuredCompletionModelDefaultParams
): string | undefined {
  const systemPrompt = modelDefaultParams.messages_template?.find(
    message => message.role === 'system'
  )?.content;
  if (typeof systemPrompt === 'string') {
    return systemPrompt;
  }
  return undefined;
}
