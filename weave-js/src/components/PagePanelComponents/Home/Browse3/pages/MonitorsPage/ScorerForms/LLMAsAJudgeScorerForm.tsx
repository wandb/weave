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
      } else {
        if (!judgeModelName) {
          setJudgeModelError('A judge model name is required.');
          return false;
        }
        // Allow empty system prompts?
        /*if (
          !judgeModel.default_params ||
          !getSystemPrompt(judgeModel.default_params)
        ) {
          setJudgeModelError('A judge model system prompt is required');
          return false;
        }*/
        if (!responseFormat) {
          setJudgeModelError('A judge model response format is required.');
          return false;
        }
      }
      return true;
    }, [judgeModel, judgeModelName, responseFormat]);

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
      if (modelHasChanged) {
        judgeModelRef = await saveModel();
        if (!judgeModelRef) {
          setJudgeModelError('Failed to save judge model.');
          return undefined;
        }
      } else {
        judgeModelRef = `weave:///${projectId}/object/${judgeModel.name}:${judgeModel.ref?._digest}`;
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
          newJudgeModel = savedModels.find(
            model =>
              model.name === savedModel.objectId &&
              model.ref?._extra?.[0] === `${savedModel.versionIndex}`
          );
        } else {
          newJudgeModel = {
            llm_model_id: newValue,
            name: judgeModelName || `${scorerName}-judge-model`,
            default_params: {
              max_tokens: maxTokens,
            },
            description: '',
            ref: undefined,
          };
        }
        setJudgeModel(newJudgeModel);
        onValidationChange(!!scorerName && !!scoringPrompt);
      },
      [
        judgeModelName,
        scoringPrompt,
        savedModels,
        scorerName,
        setJudgeModel,
        onValidationChange,
      ]
    );

    const onJudgeModelNameChange = useCallback(
      value => {
        setJudgeModelName(value);
        const validationResult = validateDatasetName(value);
        setJudgeModelError(validationResult.error);
        onValidationChange(
          !validationResult.error &&
            !!value &&
            !!systemPrompt &&
            !!responseFormat &&
            !!scorerName &&
            !!scoringPrompt
        );
      },
      [
        systemPrompt,
        responseFormat,
        scorerName,
        scoringPrompt,
        setJudgeModelName,
        setJudgeModelError,
        onValidationChange,
      ]
    );

    const onSystemPromptChange = useCallback(
      value => {
        setSystemPrompt(value);
        onValidationChange(
          !!value &&
            !!judgeModelName &&
            !!scorerName &&
            !!scoringPrompt &&
            !!responseFormat
        );
      },
      [
        judgeModelName,
        scorerName,
        scoringPrompt,
        responseFormat,
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

          <Box>
            <FieldName name="Judge model" />
            <LLMDropdownLoaded
              className="w-full"
              value={selectedJudgeModel || ''}
              isTeamAdmin={false}
              direction={{horizontal: 'left'}}
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
            <Box className="flex flex-col gap-16 rounded-md bg-moon-100 p-16">
              <Typography
                sx={typographyStyle}
                className="text-sm font-semibold uppercase tracking-wide text-moon-500">
                Model settings
              </Typography>

              <Box>
                <FieldName name="LLM ID" />
                <Typography sx={{...typographyStyle, color: 'text.secondary'}}>
                  {judgeModel.llm_model_id}
                </Typography>
              </Box>
              <Box>
                <FieldName name="Configuration name" />
                <TextField
                  value={judgeModelName}
                  onChange={onJudgeModelNameChange}
                />
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
                    (responseFormat ||
                      'json_object') as PlaygroundResponseFormats
                  }
                  setResponseFormat={setResponseFormat}
                />
              </Box>
            </Box>
          )}
          <Box>
            <FieldName name="Scoring prompt" />
            <TextArea
              value={scoringPrompt}
              placeholder="Enter a scoring prompt. You can interpolate input and output values from your op."
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
              You can interpolate input and output values from your op. See{' '}
              <Link
                to="https://wandb.me/prompt-variables"
                target="_blank"
                className="text-blue-500">
                documentation
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
