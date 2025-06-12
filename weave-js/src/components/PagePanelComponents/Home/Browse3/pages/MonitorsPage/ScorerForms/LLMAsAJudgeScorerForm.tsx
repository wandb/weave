import {Box, Typography} from '@mui/material';
import {TextArea} from '@wandb/weave/components/Form/TextArea';
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {Link} from 'react-router-dom';
import {
  FieldName,
  typographyStyle,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/FormComponents';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3';
import {useLeafObjectInstances} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/objectClassQuery';
import {ObjectVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {Select} from '@wandb/weave/components/Form/Select';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {validateDatasetName} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/datasets/datasetNameValidation';

export const LLMAsAJudgeScorerForm = ({
  scorer,
  onChange,
  onValidationChange,
}: {
  scorer: ObjectVersionSchema;
  onChange?: (scorer: ObjectVersionSchema) => void;
  onValidationChange?: (isValid: boolean) => void;
}) => {
  const [scoringPrompt, setScoringPrompt] = useState<string | undefined>(
    scorer.val['scoring_prompt']
  );
  const [judgeModelRef, setJudgeModelRef] = useState<string | undefined>(
    scorer.val['model']
  );
  const [scorerName, setScorerName] = useState<string | undefined>(
    scorer.objectId
  );
  const [nameError, setNameError] = useState<string | null>(null);

  // This is to propagate the validation state to the parent form
  useEffect(() => {
    if (onValidationChange) {
      onValidationChange(
        !!scoringPrompt && !!judgeModelRef && !!scorerName && !nameError
      );
    }
  }, [scoringPrompt, judgeModelRef, scorerName, nameError, onValidationChange]);

  const {projectId, entity, project} = useEntityProject();

  const {result: savedModels, loading: savedModelsLoading} =
    useLeafObjectInstances('LLMStructuredCompletionModel', {
      project_id: projectId,
    });

  const modelOptions = useMemo(() => {
    return (
      savedModels?.map(model => ({
        label: model.val['name'] as string,
        ref: `weave:///${projectId}/object/${model.val['name']}:${model.digest}`,
      })) ?? []
    );
  }, [savedModels]);

  const selectedModel = useMemo(() => {
    return modelOptions.find(option => option.ref === judgeModelRef);
  }, [modelOptions, judgeModelRef]);

  const onChangeCallback = useCallback(
    (scoringPrompt?: string, judgeModelRef?: string, scorerName?: string) => {
      if (!onChange) {
        //} || !scoringPrompt || !judgeModelRef || !scorerName) {
        return;
      }

      // If the scoring prompt or judge model has changed, we need to create a new scorer version
      const versionHash =
        scoringPrompt !== scorer.val['scoring_prompt'] ||
        judgeModelRef !== scorer.val['model'] ||
        scorerName !== scorer.objectId
          ? ''
          : scorer.versionHash;

      const newScorer: ObjectVersionSchema = {
        ...scorer,
        versionHash,
        objectId: scorerName || 'LLMAsAJudgeScorer',
        baseObjectClass: 'LLMAsAJudgeScorer',
        val: {
          ...scorer?.val,
          _type: 'LLMAsAJudgeScorer',
          _class_name: 'LLMAsAJudgeScorer',
          name: scorerName,
          model: judgeModelRef,
          scoring_prompt: scoringPrompt,
        },
      };
      onChange(newScorer);
    },
    [onChange, scorer, entity, project]
  );

  const onScorerNameChange = useCallback(
    (value: string) => {
      setScorerName(value);
      const validationResult = validateDatasetName(value);
      setNameError(validationResult.error);
      onChangeCallback(scoringPrompt, judgeModelRef, value);
    },
    [onChangeCallback, scoringPrompt, judgeModelRef]
  );

  return (
    <Box className="mb-2 flex flex-col gap-8">
      <Typography sx={typographyStyle} className="font-semibold">
        LLM-as-a-Judge configuration
      </Typography>
      <Box>
        <FieldName name="Name" />
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
          className="mt-1 text-sm font-normal"
          sx={{
            ...typographyStyle,
            color: 'text.secondary',
          }}>
          Valid names must start with a letter or number and can only contain
          letters, numbers, hyphens, and underscores.
        </Typography>
      </Box>
      <Box>
        <FieldName name="Judge Model" />
        {!savedModelsLoading && modelOptions.length === 0 ? (
          <Typography sx={typographyStyle} className="text-sm">
            No saved models found. Create one in the Playground.
            <br />
            See{' '}
            <Link
              to="https://docs.wandb.ai/guides/monitors/scorers#llm-as-a-judge-scorer"
              target="_blank"
              className="text-blue-500">
              docs
            </Link>{' '}
            for more details.
          </Typography>
        ) : (
          <Select<{label: string; ref: string}, false>
            isDisabled={savedModelsLoading}
            placeholder={
              savedModelsLoading ? 'Loading...' : 'Select a judge model'
            }
            options={modelOptions}
            value={selectedModel}
            onChange={newValue => {
              setJudgeModelRef(newValue?.ref);
              onChangeCallback(scoringPrompt, newValue?.ref, scorerName);
            }}
          />
        )}
      </Box>
      <Box>
        <FieldName name="Scoring Prompt" />
        <TextArea
          value={scoringPrompt}
          placeholder="Enter a scoring prompt. You can use the following variables: {output} and {input}."
          onChange={e => {
            setScoringPrompt(e.target.value);
            onChangeCallback(e.target.value, judgeModelRef, scorerName);
          }}
        />
        <Typography
          className="mt-1 text-sm font-normal"
          sx={{
            ...typographyStyle,
            color: 'text.secondary',
          }}>
          The scoring prompt will be used to score the output of your ops. You
          can use the following variables: {'{output}'} and {'{input}'}. See{' '}
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
  );
};
