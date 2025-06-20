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
  ({scorer, onValidationChange, validationErrors}, ref) => {
    console.log('LLMAsAJudgeScorerForm rendered with:', {
      scorer,
      validationErrors
    });
    
    // Track which fields have been touched
    const [touchedFields, setTouchedFields] = useState<{
      scorerName?: boolean;
      scoringPrompt?: boolean;
      judgeModel?: boolean;
      judgeModelName?: boolean;
      systemPrompt?: boolean;
    }>({});
    
    // When validationErrors are provided, it means the form was submitted
    // So we should show all validation errors
    useEffect(() => {
      if (validationErrors && validationErrors.scorerName) {
        setTouchedFields({
          scorerName: true,
          scoringPrompt: true,
          judgeModel: true,
          judgeModelName: true,
          systemPrompt: true
        });
        
        // Trigger validation for all fields
        if (!scorerName) setNameError('Scorer name is required');
        if (!scoringPrompt) setScoringPromptError('Scoring prompt is required');
        if (!judgeModel) setJudgeModelError('Judge model is required');
        if (!judgeModelName) setJudgeModelNameError('Judge model configuration name is required');
        if (!systemPrompt) setSystemPromptError('System prompt is required');
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [validationErrors]);
    //const [isValid, setIsValid] = useState(false);
    const [scorerName, setScorerName] = useState<string | undefined>(
      scorer.objectId || ''
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
    const [judgeModelNameError, setJudgeModelNameError] = useState<
      string | null
    >(null);

    const [systemPrompt, setSystemPrompt] = useState<string | undefined>();
    const [systemPromptError, setSystemPromptError] = useState<string | null>(
      null
    );

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

    // Properly validate on mount and when dependencies change
    useEffect(() => {
      console.log('LLMAsAJudgeScorerForm validation check:', {
        scorerName,
        scoringPrompt,
        judgeModel,
        judgeModelName,
        systemPrompt,
        responseFormat
      });
      
      // Call validation with current state
      const isValid = !!scorerName && !!scoringPrompt && !!judgeModel && 
                      !!judgeModelName && !!systemPrompt && !!responseFormat;
      console.log('Validation result:', isValid);
      onValidationChange(isValid);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scorerName, scoringPrompt, judgeModel, judgeModelName, systemPrompt, responseFormat]);
    
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
      let isValid = true;

      if (!judgeModel) {
        setJudgeModelError('Judge model is required');
        isValid = false;
      } else {
        setJudgeModelError(null);
      }

      if (!judgeModelName) {
        setJudgeModelNameError('Judge model configuration name is required');
        isValid = false;
      } else {
        setJudgeModelNameError(null);
      }

      if (!systemPrompt) {
        setSystemPromptError('Judge model system prompt is required');
        isValid = false;
      } else {
        setSystemPromptError(null);
      }

      if (!responseFormat) {
        // This error shows on the judge model field since response format is part of the model config
        if (judgeModel && !judgeModelError) {
          setJudgeModelError('Judge model response format is required');
        }
        isValid = false;
      }

      return isValid;
    }, [
      judgeModel,
      judgeModelName,
      responseFormat,
      systemPrompt,
      judgeModelError,
    ]);

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
        setNameError(null); // Clear error when name is valid
      }
      if (!scoringPrompt) {
        setScoringPromptError('A scoring prompt is required.');
        return false;
      }
      setScoringPromptError(null); // Clear error when prompt is valid
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
        setTouchedFields(prev => ({ ...prev, scorerName: true }));
        setNameError(null);
        const validationResult = validateDatasetName(value);
        if (validationResult.error) {
          setNameError(validationResult.error);
        } else if (!value) {
          setNameError('Scorer name is required');
        }
        const isValid =
          !validationResult.error &&
          !!value &&
          !!scoringPrompt &&
          !!judgeModel &&
          !!judgeModelName &&
          !!responseFormat &&
          !!systemPrompt;
        console.log('onScorerNameChange validation:', {
          value,
          scoringPrompt: !!scoringPrompt,
          judgeModel: !!judgeModel,
          judgeModelName: !!judgeModelName,
          responseFormat: !!responseFormat,
          systemPrompt: !!systemPrompt,
          isValid
        });
        onValidationChange(isValid);
      },
      [
        scoringPrompt,
        judgeModel,
        judgeModelName,
        responseFormat,
        systemPrompt,
        onValidationChange,
      ]
    );

    useEffect(() => {
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
        setTouchedFields(prev => ({ ...prev, judgeModel: true }));
        setJudgeModelError(null);
        // Validate all fields when judge model changes
        const isValid =
          !!scorerName &&
          !!scoringPrompt &&
          !!newJudgeModel &&
          !!judgeModelName &&
          !!responseFormat &&
          !!systemPrompt;
        console.log('onJudgeModelChange validation:', {
          scorerName: !!scorerName,
          scoringPrompt: !!scoringPrompt,
          newJudgeModel: !!newJudgeModel,
          judgeModelName: !!judgeModelName,
          responseFormat: !!responseFormat,
          systemPrompt: !!systemPrompt,
          isValid
        });
        onValidationChange(isValid);
      },
      [
        judgeModelName,
        scoringPrompt,
        savedModels,
        scorerName,
        setJudgeModel,
        onValidationChange,
        responseFormat,
        systemPrompt,
      ]
    );

    const onJudgeModelNameChange = useCallback(
      value => {
        setJudgeModelName(value);
        setTouchedFields(prev => ({ ...prev, judgeModelName: true }));
        setJudgeModelNameError(null);
        const validationResult = validateDatasetName(value);
        if (validationResult.error) {
          setJudgeModelNameError(validationResult.error);
        } else if (!value) {
          setJudgeModelNameError('Judge model configuration name is required');
        }
        onValidationChange(
          !validationResult.error &&
            !!value &&
            !!responseFormat &&
            !!scorerName &&
            !!scoringPrompt &&
            !!judgeModel &&
            !!systemPrompt
        );
      },
      [
        responseFormat,
        scorerName,
        scoringPrompt,
        judgeModel,
        systemPrompt,
        onValidationChange,
      ]
    );

    const onSystemPromptChange = useCallback(
      value => {
        setSystemPrompt(value);
        setTouchedFields(prev => ({ ...prev, systemPrompt: true }));
        setSystemPromptError(null);
        if (!value) {
          setSystemPromptError('System prompt is required');
        }
        // System prompt is now required
        onValidationChange(
          !!value &&
            !!judgeModelName &&
            !!scorerName &&
            !!scoringPrompt &&
            !!responseFormat &&
            !!judgeModel
        );
      },
      [
        judgeModelName,
        scorerName,
        scoringPrompt,
        responseFormat,
        judgeModel,
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
            {(touchedFields.scorerName || validationErrors?.scorerName) && nameError && (
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
            <FieldName name="Judge Model" />
            <LLMDropdownLoaded
              className="w-full"
              value={selectedJudgeModel || ''}
              isTeamAdmin={false}
              direction={{horizontal: 'left', vertical: 'up'}}
              onChange={onJudgeModelChange}
            />
            {(touchedFields.judgeModel || validationErrors?.judgeModel) && judgeModelError && (
              <Typography
                className="mt-1 text-sm"
                sx={{
                  ...typographyStyle,
                  color: 'error.main',
                }}>
                {judgeModelError}
              </Typography>
            )}
          </Box>
          {judgeModel && (
            <Box className="flex flex-col gap-8 rounded-md border border-moon-250 p-12">
              <Box>
                <FieldName name="LLM ID" />
                <Typography sx={{...typographyStyle, color: 'text.secondary'}}>
                  {judgeModel.llm_model_id}
                </Typography>
              </Box>
              <Box>
                <FieldName name="Judge Model Configuration Name" />
                <TextField
                  value={judgeModelName}
                  onChange={onJudgeModelNameChange}
                />
                {(touchedFields.judgeModelName || validationErrors?.judgeModelName) && judgeModelNameError && (
                  <Typography
                    className="mt-1 text-sm"
                    sx={{
                      ...typographyStyle,
                      color: 'error.main',
                    }}>
                    {judgeModelNameError}
                  </Typography>
                )}
              </Box>
              <Box>
                <FieldName name="Judge Model System Prompt" />
                <TextArea
                  value={systemPrompt}
                  onChange={e => onSystemPromptChange(e.target.value)}
                />
                {(touchedFields.systemPrompt || validationErrors?.systemPrompt) && systemPromptError && (
                  <Typography
                    className="mt-1 text-sm"
                    sx={{
                      ...typographyStyle,
                      color: 'error.main',
                    }}>
                    {systemPromptError}
                  </Typography>
                )}
              </Box>
              <Box>
                <FieldName name="Judge Model Response Format" />
                <ResponseFormatSelect
                  responseFormat={
                    (responseFormat ||
                      'json_object') as PlaygroundResponseFormats
                  }
                  setResponseFormat={value => {
                    setResponseFormat(value);
                    // Trigger validation when response format changes
                    const isValid =
                      !!scorerName &&
                      !!scoringPrompt &&
                      !!judgeModel &&
                      !!judgeModelName &&
                      !!value &&
                      !!systemPrompt;
                    onValidationChange(isValid);
                  }}
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
                setTouchedFields(prev => ({ ...prev, scoringPrompt: true }));
                setScoringPromptError(null);
                if (!e.target.value) {
                  setScoringPromptError('Scoring prompt is required');
                }
                onValidationChange(
                  !!e.target.value && !!scorerName && validateJudgeModel()
                );
              }}
            />
            {(touchedFields.scoringPrompt || validationErrors?.scoringPrompt) && scoringPromptError && (
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
