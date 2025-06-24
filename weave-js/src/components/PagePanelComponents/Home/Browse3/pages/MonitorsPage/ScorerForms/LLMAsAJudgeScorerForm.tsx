import {Box, Typography} from '@mui/material';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/context';
import {validateDatasetName} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/datasets/datasetNameValidation';
import {
  FieldName,
  typographyStyle,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/FormComponents';
import React, {
  forwardRef,
  useCallback,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';
import {Link} from 'react-router-dom';

import {LlmStructuredCompletionModel} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {useScorerCreate} from '../../wfReactInterface/tsDataModelHooks';
import {ScorerFormProps, ScorerFormRef} from '../MonitorFormDrawer';
import {
  ModelConfigurationForm,
  ModelConfigurationFormRef,
} from './ModelConfigurationForm';

export const LLMAsAJudgeScorerForm = forwardRef<ScorerFormRef, ScorerFormProps>(
  ({scorer, onValidationChange}, ref) => {
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

    const [modelFormValid, setModelFormValid] = useState(false);

    const {projectId, entity, project} = useEntityProject();

    const modelFormRef = useRef<ModelConfigurationFormRef | null>(null);

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
      if (!modelFormValid) {
        return false;
      }
      return true;
    }, [scorerName, scoringPrompt, modelFormValid]);

    const scorerCreate = useScorerCreate();

    const saveScorer = useCallback(async (): Promise<string | undefined> => {
      if (!validateScorer() || !judgeModel || !scorerName) {
        return undefined;
      }

      // Save the model first if needed
      const judgeModelRef = await modelFormRef.current?.saveModel();
      if (!judgeModelRef) {
        return undefined;
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
          !validationResult.error && modelFormValid && !!scoringPrompt
        );
      },
      [scoringPrompt, modelFormValid, onValidationChange]
    );

    const onModelValidationChange = useCallback(
      (isValid: boolean) => {
        setModelFormValid(isValid);
        onValidationChange(!nameError && isValid && !!scoringPrompt);
      },
      [nameError, scoringPrompt, onValidationChange]
    );

    const onModelChange = useCallback(
      (model: LlmStructuredCompletionModel | undefined) => {
        setJudgeModel(model);
      },
      []
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

          <ModelConfigurationForm
            ref={modelFormRef}
            initialModelRef={scorer.val['model']}
            onValidationChange={onModelValidationChange}
            onModelChange={onModelChange}
          />

          <Box>
            <FieldName name="Scoring prompt" />
            <TextArea
              value={scoringPrompt}
              placeholder="Enter a scoring prompt. You can use the following variables: {output} and {input}."
              onChange={e => {
                setScoringPrompt(e.target.value);
                onValidationChange(
                  !!e.target.value && !!scorerName && modelFormValid
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
