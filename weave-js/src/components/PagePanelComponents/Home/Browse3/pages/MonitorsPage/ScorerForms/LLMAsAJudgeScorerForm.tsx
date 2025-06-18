import {Box, Typography} from '@mui/material';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {
  FieldName,
  typographyStyle,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/FormComponents';
import {transformToValidName} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/nameTransformUtils';
import {
  useCreateBuiltinObjectInstance,
  useLeafObjectInstances,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/objectClassQuery';
import {Tailwind} from '@wandb/weave/components/Tailwind';
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

    const [hasNameTransform, setHasNameTransform] = useState<boolean>(false);
    const [transformedScorerName, setTransformedScorerName] =
      useState<string>('');

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
    const [transformedJudgeModelName, setTransformedJudgeModelName] =
      useState<string>('');
    const [hasJudgeModelNameTransform, setHasJudgeModelNameTransform] =
      useState<boolean>(false);

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
      if (!transformedScorerName) {
        return false;
      }
      if (!scoringPrompt) {
        setScoringPromptError('A scoring prompt is required.');
        return false;
      }
      if (!validateJudgeModel()) {
        return false;
      }
      return true;
    }, [transformedScorerName, scoringPrompt, validateJudgeModel]);

    const createLLMStructuredCompletionModel = useCreateBuiltinObjectInstance(
      'LLMStructuredCompletionModel'
    );

    const saveModel = useCallback(async (): Promise<string | undefined> => {
      if (!judgeModel) {
        return undefined;
      }

      const model: LlmStructuredCompletionModel = {
        llm_model_id: judgeModel.llm_model_id,
        name: transformedJudgeModelName,
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
      transformedJudgeModelName,
      systemPrompt,
      responseFormat,
      createLLMStructuredCompletionModel,
    ]);

    const scorerCreate = useScorerCreate();

    const saveScorer = useCallback(async (): Promise<string | undefined> => {
      if (!validateScorer() || !judgeModel || !transformedScorerName) {
        return undefined;
      }

      const modelHasChanged =
        transformedJudgeModelName !== judgeModel.name ||
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
        transformedScorerName !== scorer.objectId;

      let scorerDigest: string;
      if (!scorerHasChanged) {
        scorerDigest = scorer.versionHash;
      } else {
        const val = {
          _type: 'LLMAsAJudgeScorer',
          _class_name: 'LLMAsAJudgeScorer',
          _bases: ['Scorer', 'Object', 'BaseModel'],
          name: transformedScorerName,
          model: judgeModelRef,
          scoring_prompt: scoringPrompt,
        };
        const response = await scorerCreate({
          entity,
          project,
          name: transformedScorerName,
          val,
        });
        scorerDigest = response.versionHash;
      }

      return `weave:///${projectId}/object/${transformedScorerName}:${scorerDigest}`;
    }, [
      validateScorer,
      scorer,
      transformedScorerName,
      scoringPrompt,
      judgeModel,
      scorerCreate,
      projectId,
      entity,
      project,
      saveModel,
      transformedJudgeModelName,
      systemPrompt,
      responseFormat,
    ]);

    useImperativeHandle(ref, () => ({
      saveScorer,
    }));

    const onScorerNameChange = useCallback(
      (value: string) => {
        setScorerName(value);
        const transformResult = transformToValidName(value);
        setTransformedScorerName(transformResult.transformedName);
        setHasNameTransform(transformResult.hasChanged);
        onValidationChange(
          !!transformResult.transformedName &&
            validateJudgeModel() &&
            !!scoringPrompt
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
            name: judgeModelName || `${transformedScorerName}-judge-model`,
            default_params: {
              max_tokens: maxTokens,
            },
            description: '',
            ref: undefined,
          };
        }
        setJudgeModel(newJudgeModel);
        onValidationChange(!!transformedScorerName && !!scoringPrompt);
      },
      [
        judgeModelName,
        scoringPrompt,
        savedModels,
        transformedScorerName,
        setJudgeModel,
        onValidationChange,
      ]
    );

    const onJudgeModelNameChange = useCallback(
      value => {
        setJudgeModelName(value);
        const transformResult = transformToValidName(value);
        setTransformedJudgeModelName(transformResult.transformedName);
        setHasJudgeModelNameTransform(transformResult.hasChanged);
        setJudgeModelError(null);
        onValidationChange(
          !!transformResult.transformedName &&
            !!systemPrompt &&
            !!responseFormat &&
            !!transformedScorerName &&
            !!scoringPrompt
        );
      },
      [
        systemPrompt,
        responseFormat,
        transformedScorerName,
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
            !!transformedScorerName &&
            !!scoringPrompt &&
            !!responseFormat
        );
      },
      [
        judgeModelName,
        transformedScorerName,
        scoringPrompt,
        responseFormat,
        onValidationChange,
      ]
    );

    return (
      <Tailwind>
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
              {hasNameTransform && (
                <Typography
                  className="mt-4 text-sm"
                  sx={{
                    ...typographyStyle,
                    color: 'sienna',
                  }}>
                  Your scorer name will be saved as{' '}
                  <span style={{fontWeight: 600}}>{transformedScorerName}</span>
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
              <FieldName name="Judge Model" />
              <LLMDropdownLoaded
                className="w-full"
                value={selectedJudgeModel || ''}
                isTeamAdmin={false}
                direction={{horizontal: 'left', vertical: 'up'}}
                onChange={onJudgeModelChange}
              />
              {judgeModelError && (
                <Typography
                  className="mt-4 text-sm"
                  sx={{
                    ...typographyStyle,
                    color: 'info.warning',
                  }}
                />
              )}
            </Box>
            {judgeModel && (
              <Box className="flex flex-col gap-8 rounded-md border border-moon-250 p-12">
                <Box>
                  <FieldName name="LLM ID" />
                  <Typography
                    sx={{...typographyStyle, color: 'text.secondary'}}>
                    {judgeModel.llm_model_id}
                  </Typography>
                </Box>
                <Box>
                  <FieldName name="Judge Model Configuration Name" />
                  <TextField
                    value={judgeModelName}
                    onChange={onJudgeModelNameChange}
                  />
                  {hasJudgeModelNameTransform && (
                    <Typography
                      className="mt-4 text-sm"
                      sx={{
                        ...typographyStyle,
                        color: 'sienna',
                      }}>
                      Your model name will be saved as{' '}
                      <span style={{fontWeight: 600}}>
                        {transformedJudgeModelName}
                      </span>
                    </Typography>
                  )}
                </Box>
                <Box>
                  <FieldName name="Judge Model System Prompt" />
                  <TextArea
                    value={systemPrompt}
                    onChange={e => onSystemPromptChange(e.target.value)}
                  />
                </Box>
                <Box>
                  <FieldName name="Judge Model Response Format" />
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
              <FieldName name="Scoring Prompt" />
              <TextArea
                value={scoringPrompt}
                placeholder="Enter a scoring prompt. You can use the following variables: {output} and {input}."
                onChange={e => {
                  setScoringPrompt(e.target.value);
                  onValidationChange(
                    !!e.target.value &&
                      !!transformedScorerName &&
                      validateJudgeModel()
                  );
                }}
              />
              {scoringPromptError && (
                <Typography
                  className="mt-1 text-sm"
                  sx={{
                    ...typographyStyle,
                    color: 'error.main',
                  }}>
                  {scoringPromptError}
                </Typography>
              )}
              <Typography
                className="mt-1 text-sm font-normal"
                sx={{
                  ...typographyStyle,
                  color: 'text.secondary',
                }}>
                The scoring prompt will be used to score the output of your ops.
                You can use the following variables: {'{output}'} and{' '}
                {'{input}'}. See{' '}
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
      </Tailwind>
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
