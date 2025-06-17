import {Box, Typography} from '@mui/material';
import {Button} from '@wandb/weave/components/Button';
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
import {Link} from 'react-router-dom';

import {LLMDropdownLoaded} from '../../PlaygroundPage/PlaygroundChat/LLMDropdown';
import {ResponseFormatSelect} from '../../PlaygroundPage/PlaygroundSettings/ResponseFormatEditor';
import {PlaygroundResponseFormats} from '../../PlaygroundPage/types';
import {
  LlmStructuredCompletionModel,
  LlmStructuredCompletionModelDefaultParams,
  ResponseFormat,
} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {useScorerCreate} from '../../wfReactInterface/tsDataModelHooks';
import {ScorerFormProps, ScorerFormRef} from '../MonitorFormDrawer';

export const LLMAsAJudgeScorerForm = forwardRef<ScorerFormRef, ScorerFormProps>(
  ({scorer, onValidationChange}, ref) => {
    //const [isValid, setIsValid] = useState(false);
    const [scorerName, setScorerName] = useState<string | undefined>(
      scorer.objectId
    );

    const [nameError, setNameError] = useState<string | null>(null);

    const [scoringPrompt, setScoringPrompt] = useState<string | undefined>(
      scorer.val['scoring_prompt']
    );

    const [scoringPromptError, setScoringPromptError] = useState<string | null>(
      null
    );

    const [judgeModel, setJudgeModel] = useState<
      LlmStructuredCompletionModel | undefined
    >(undefined);

    const [judgeModelError, setJudgeModelError] = useState<string | null>(null);

    const [judgeModelName, setJudgeModelName] = useState<string | undefined>();

    const [systemPrompt, setSystemPrompt] = useState<string | undefined>();

    const [responseFormat, setResponseFormat] = useState<
      ResponseFormat | undefined
    >();

    const [isProviderModel, setIsProviderModel] = useState<boolean>(false);

    const [isModelSettingsExpanded, setIsModelSettingsExpanded] = useState<boolean>(true);

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
          // Createing a ref so we can track the version index
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

    useEffect(() => {
      if (!savedModels || !scorer.val['model']) {
        return;
      }
      const currentModel = savedModels.find(
        model =>
          `weave:///${projectId}/object/${model.name}:${model.ref?._digest}` ===
          scorer.val['model']
      );
      if (currentModel) {
        setJudgeModel(currentModel);
        setIsProviderModel(false);
        onValidationChange(true);
        if (currentModel.default_params) {
          const systemPrompt = getSystemPrompt(currentModel.default_params);
          setSystemPrompt(systemPrompt);
        }
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [savedModels, entity, project, projectId, scorer.val]);

    const selectedJudgeModel = useMemo(() => {
      if (judgeModel) {
        if (judgeModel.ref) {
          // This is a saved model
          return `${judgeModel.name}:v${judgeModel.ref?._extra?.[0]}`;
        }
        return judgeModel.llm_model_id;
      }
      return undefined;
    }, [judgeModel]);

    const validateJudgeModel = useCallback(() => {
      if (!judgeModel) {
        setJudgeModelError('A judge model is required.');
        return false;
      }
      setJudgeModelError(null);
      return true;
    }, [judgeModel]);

    const validateScorer = useCallback(() => {
      if (!scorerName) {
        setNameError('A scorer name is required.');
        return false;
      } else {
        const validationResult = validateDatasetName(scorerName);
        if (validationResult.error) {
          setNameError(validationResult.error);
          return false;
        }
      }
      if (!scoringPrompt) {
        setScoringPromptError('A scoring prompt is required.');
        return false;
      }
      if (!validateJudgeModel()) {
        return false;
      }
      return true;
    }, [scorerName, scoringPrompt, validateJudgeModel]);

    const createLLMStructuredCompletionModel = useCreateBuiltinObjectInstance(
      'LLMStructuredCompletionModel'
    );

    const saveModel = useCallback(async (): Promise<string | undefined> => {
      if (!judgeModel) {
        return undefined;
      }

      // Check if this model already exists in saved models
      const existingModel = savedModels.find(
        model => model.name === judgeModelName
      );
      
      if (existingModel) {
        // Model already exists, return its reference
        return `weave:///${projectId}/object/${existingModel.name}:${existingModel.ref?._digest}`;
      }

      const model: LlmStructuredCompletionModel = {
        llm_model_id: judgeModel.llm_model_id,
        name: judgeModelName,
        default_params: {
          ...judgeModel.default_params,
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
            object_id: model.name as string,
            val: model,
          },
        });
        console.log('saveModel', 'post response', response);
        return `weave:///${projectId}/object/${model.name}:${response.digest}`;
      } catch (error) {
        console.error('Failed to save model:', error);
      }
      return undefined;
    }, [
      projectId,
      judgeModel,
      judgeModelName,
      systemPrompt,
      responseFormat,
      createLLMStructuredCompletionModel,
      savedModels,
    ]);

    const scorerCreate = useScorerCreate();

    const saveScorer = useCallback(async (): Promise<string | undefined> => {
      if (!validateScorer() || !judgeModel || !scorerName) {
        return undefined;
      }

      const modelHasChanged =
        judgeModelName !== judgeModel.name ||
        systemPrompt !== getSystemPrompt(judgeModel.default_params || {}) ||
        responseFormat !== judgeModel.default_params?.response_format;

      let judgeModelRef: string | undefined;
      if (modelHasChanged && !judgeModel.ref) {
        // Only save the model if it's changed and it's not already a saved model
        judgeModelRef = await saveModel();
        if (!judgeModelRef) {
          setJudgeModelError('Failed to save judge model.');
          return undefined;
        }
      } else if (judgeModel.ref) {
        // This is already a saved model, use its reference
        judgeModelRef = `weave:///${projectId}/object/${judgeModel.name}:${judgeModel.ref?._digest}`;
      } else {
        // Model hasn't changed and it's a provider model that needs to be saved
        judgeModelRef = await saveModel();
        if (!judgeModelRef) {
          setJudgeModelError('Failed to save judge model.');
          return undefined;
        }
      }

      // If the scoring prompt or judge model has changed, we need to create a new scorer version
      const scorerHasChanged =
        scoringPrompt !== scorer.val['scoring_prompt'] ||
        judgeModelRef !== scorer.val['model'] ||
        scorerName !== scorer.objectId;

      let scorerDigest: string;
      if (!scorerHasChanged) {
        scorerDigest = scorer.versionHash;
      } else {
        const val = {
          _type: 'LLMAsAJudgeScorer',
          _class_name: 'LLMAsAJudgeScorer',
          _bases: ['Scorer', 'Object', 'BaseModel'],
          name: scorerName,
          model: judgeModelRef,
          scoring_prompt: scoringPrompt,
        };
        const response = await scorerCreate({
          entity,
          project,
          name: scorerName,
          val,
        });
        scorerDigest = response.versionHash;
      }

      return `weave:///${projectId}/object/${scorerName}:${scorerDigest}`;
    }, [
      validateScorer,
      scorer,
      scorerName,
      scoringPrompt,
      judgeModel,
      scorerCreate,
      projectId,
      entity,
      project,
      saveModel,
      judgeModelName,
      systemPrompt,
      responseFormat,
    ]);

    useImperativeHandle(ref, () => ({
      saveScorer,
    }));

    const onScorerNameChange = useCallback(
      (value: string) => {
        setScorerName(value);
        const validationResult = validateDatasetName(value);
        setNameError(validationResult.error);
        onValidationChange(
          !validationResult.error && validateJudgeModel() && !!scoringPrompt
        );
      },
      [scoringPrompt, validateJudgeModel, onValidationChange]
    );

    useMemo(() => {
      setJudgeModelName(judgeModel?.name || undefined);
      setSystemPrompt(
        judgeModel?.default_params && getSystemPrompt(judgeModel.default_params)
      );
      setResponseFormat(
        judgeModel?.default_params?.response_format || 'json_object'
      );
    }, [judgeModel]);

    const onJudgeModelChange = useCallback(
      (newValue, maxTokens, savedModel) => {
        let newJudgeModel: LlmStructuredCompletionModel | undefined;

        if (savedModel && savedModels) {
          // This is a saved model - use its existing configuration
          newJudgeModel = savedModels.find(
            model =>
              model.name === savedModel.objectId &&
              model.ref?._extra?.[0] === `${savedModel.versionIndex}`
          );
          setIsProviderModel(false);
        } else {
          // This is a provider model - create default judge model configuration
          const modelName = `${newValue}-judge-model-default`;
          const defaultSystemPrompt = `
You are an impartial evaluation system designed to assess outputs according to provided criteria. You will receive specific evaluation instructions and must follow them precisely.

CRITICAL: You must ALWAYS respond in valid JSON format using the exact structure specified in the evaluation instructions. Never deviate from the required JSON format under any circumstances.

Your role:
1. Carefully read the evaluation criteria provided
2. Analyze the given output objectively against those criteria
3. Focus solely on the specified evaluation dimensions
4. Provide your assessment in the exact JSON format requested

Remember: Your response must be valid JSON that can be parsed programmatically. Do not include any text outside the JSON structure.
`.trim();
          
          newJudgeModel = {
            llm_model_id: newValue,
            name: modelName,
            default_params: {
              max_tokens: maxTokens,
              messages_template: [{role: 'system', content: defaultSystemPrompt}],
              response_format: 'json_object',
            },
            description: '',
            ref: undefined,
          };
          setIsProviderModel(true);
        }
        setJudgeModel(newJudgeModel);
        onValidationChange(!!scorerName && !!scoringPrompt);
      },
      [
        scoringPrompt,
        savedModels,
        scorerName,
        setJudgeModel,
        onValidationChange,
      ]
    );


    return (
      <Box className="flex flex-col gap-8 pt-16">
        <Typography
          sx={typographyStyle}
          className="border-t border-moon-250 px-20 pb-8 pt-16 font-semibold uppercase tracking-wide text-moon-500">
          LLM-as-a-Judge configuration
        </Typography>

        <Box className="flex flex-col gap-16 px-20">
          <Box>
            <FieldName name="Scorer Name" />
            <TextField value={scorerName} onChange={onScorerNameChange} />
            {nameError && (
              <Typography
                className="mt-1 text-sm"
                sx={{
                  ...typographyStyle,
                  color: 'error.main',
                }}>
                {nameError}
              </Typography>
            )}
            <Typography
              className="mt-4 text-sm font-normal"
              sx={{
                ...typographyStyle,
                color: 'text.secondary',
              }}>
              Valid names must start with a letter or number and can only
              contain letters, numbers, hyphens, and underscores.
            </Typography>
          </Box>

          <div className="flex flex-col gap-8">
            <Box>
              <FieldName name="Judge model" />
              <LLMDropdownLoaded
                className="w-full"
                value={selectedJudgeModel || ''}
                isTeamAdmin={false}
                direction={{horizontal: 'left', vertical: 'up'}}
                onChange={onJudgeModelChange}
              />
              {judgeModelError && (
                <Typography
                  className="mt-1 text-sm"
                  sx={{
                    ...typographyStyle,
                    color: 'error.main',
                  }}
                />
              )}
            </Box>
            {judgeModel && (
              <Box className="flex flex-col gap-8 rounded-md bg-moon-100 py-8 pl-16 pr-8">
                <Box 
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setIsModelSettingsExpanded(!isModelSettingsExpanded)}
                >
                  <Typography
                    sx={typographyStyle}
                    className="text-sm font-semibold uppercase tracking-wide text-moon-500">
                    Model settings
                  </Typography>
                  <Button
                    variant="ghost"
                    size="small"
                    icon={isModelSettingsExpanded ? 'chevron-up' : 'chevron-down'}
                  />
                </Box>

                {isModelSettingsExpanded && (
                  <>
                    <Box>
                      <Typography 
                        sx={{...typographyStyle, fontWeight: 600, marginBottom: '4px'}}
                      >
                        LLM
                      </Typography>
                      <Typography sx={{...typographyStyle, color: 'text.secondary'}}>
                        {judgeModel.llm_model_id}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography 
                        sx={{...typographyStyle, fontWeight: 600, marginBottom: '4px'}}
                      >
                        Configuration name
                      </Typography>
                      <Typography sx={{...typographyStyle, color: 'text.secondary'}}>
                        {judgeModelName}
                      </Typography>
                    </Box>
                    <Box>
                      <Typography 
                        sx={{...typographyStyle, fontWeight: 600, marginBottom: '4px'}}
                      >
                        System prompt
                      </Typography>
                      <Typography sx={{...typographyStyle, color: 'text.secondary', whiteSpace: 'pre-wrap'}}>
                        {systemPrompt}
                      </Typography>
                    </Box>
                    <Box className="mb-8">
                      <Typography 
                        sx={{...typographyStyle, fontWeight: 600, marginBottom: '4px'}}
                      >
                        Response format
                      </Typography>
                      <Typography sx={{...typographyStyle, color: 'text.secondary'}}>
                        {responseFormat}
                      </Typography>
                    </Box>
                  </>
                )}
              </Box>
            )}
          </div>

          <Box>
            <FieldName name="Scoring prompt" />
            <TextArea
              value={scoringPrompt}
              placeholder="Enter a scoring prompt. You can use the following variables: {output} and {input}."
              onChange={e => {
                setScoringPrompt(e.target.value);
                onValidationChange(
                  !!e.target.value && !!scorerName && validateJudgeModel()
                );
              }}
            />
            {scoringPromptError && (
              <Typography
                className="mt-4 text-sm"
                sx={{
                  ...typographyStyle,
                  color: 'error.main',
                }}>
                {scoringPromptError}
              </Typography>
            )}
            <Typography
              className="mt-4 text-sm font-normal"
              sx={{
                ...typographyStyle,
                color: 'text.secondary',
              }}>
              The scoring prompt will be used to score the output of your ops.
              You can use the following variables: {'{output}'} and {'{input}'}.
              See{' '}
              <Link
                to="https://docs.wandb.ai/guides/monitors/scorers#llm-as-a-judge-scorer"
                target="_blank"
                className="text-blue-500">
                docs
              </Link>{' '}
              for more details.
            </Typography>
          </Box>
        </Box>
      </Box>
    );
  }
);

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
