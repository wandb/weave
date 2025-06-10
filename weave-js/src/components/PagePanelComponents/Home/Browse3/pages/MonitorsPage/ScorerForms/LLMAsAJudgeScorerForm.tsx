import {Box, TextField, Typography} from '@mui/material';
import React, {useMemo, useState} from 'react';
import {
  FieldName,
  typographyStyle,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/MonitorsPage/FormComponents';
import {useEntityProject} from '@wandb/weave/components/PagePanelComponents/Home/Browse3';
import {
  useBaseObjectInstances,
  useLeafObjectInstances,
} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/objectClassQuery';
import {useConfiguredProviders} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/useConfiguredProviders';
import {useLLMDropdownOptions} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/PlaygroundChat/LLMDropdownOptions';
import {LLMMaxTokensKey} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/llmMaxTokens';
import {SavedPlaygroundModelState} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/types';
import {LLMDropdown} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/PlaygroundPage/PlaygroundChat/LLMDropdown';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {useIsTeamAdmin} from '@wandb/weave/common/hooks/useIsTeamAdmin';
import {ObjectVersionSchema} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/wfDataModelHooksInterface';
import {useObjectVersion} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/pages/wfReactInterface/tsDataModelHooks';
import {parseRef, WeaveObjectRef} from '@wandb/weave/react';

export const LLMAsAJudgeScorerForm = ({
  scorer,
}: {
  scorer?: ObjectVersionSchema;
}) => {
  return scorer ? (
    <ModelPreloader scorer={scorer} />
  ) : (
    <LLMAsAJudgeScorerFormInner scorer={scorer} />
  );
};

const ModelPreloader = ({scorer}: {scorer: ObjectVersionSchema}) => {
  const existingModelRef = useMemo(
    () => parseRef(scorer.val['model']) as WeaveObjectRef,
    [scorer]
  );
  const {result: existingModel, loading} = useObjectVersion({
    key: {
      scheme: 'weave',
      weaveKind: 'object',
      entity: existingModelRef.entityName,
      project: existingModelRef.projectName,
      objectId: existingModelRef.artifactName,
      versionHash: existingModelRef.artifactVersion,
      path: '',
    },
  });

  return (
    <LLMAsAJudgeScorerFormInner
      modelIsLoading={loading}
      model={existingModel || undefined}
      scorer={scorer}
    />
  );
};

export const LLMAsAJudgeScorerFormInner = ({
  scorer,
  model,
  modelIsLoading,
  onChange,
}: {
  modelIsLoading?: boolean;
  scorer?: ObjectVersionSchema;
  model?: ObjectVersionSchema;
  onChange?: (scorer: ObjectVersionSchema) => void;
}) => {
  const [scoringPrompt, setScoringPrompt] = useState<string | undefined>(
    scorer?.val['scoring_prompt']
  );
  const [judgeModel, setJudgeModel] = useState<string | undefined>(
    model?.val['name']
  );
  return (
    <Box className="mb-2 flex flex-col gap-8">
      <Typography sx={typographyStyle} className="font-semibold">
        LLM-as-a-Judge configuration
      </Typography>
      <Box>
        <FieldName name="Judge Model" />
        <LLMDropdownWithOptions
          loading={modelIsLoading ?? false}
          value={judgeModel || ''}
          onChange={(model, maxTokens, savedModel) => {
            setJudgeModel(model);
          }}
        />
      </Box>
      <Box>
        <FieldName name="Scoring Prompt" />
        <TextField
          value={scoringPrompt}
          placeholder="Enter a scoring prompt. You can use the following variables: {output} and {input}."
          onChange={e => setScoringPrompt(e.target.value)}
        />
      </Box>
    </Box>
  );
};

const LLMDropdownWithOptions = ({
  value,
  onChange,
  loading,
}: {
  loading?: boolean;
  value: string | undefined;
  onChange: (
    model: LLMMaxTokensKey,
    maxTokens: number,
    savedModel: SavedPlaygroundModelState
  ) => void;
}) => {
  const {entity, project, projectId} = useEntityProject();
  const {
    result: configuredProviders,
    loading: configuredProvidersLoading,
    refetch: refetchConfiguredProviders,
  } = useConfiguredProviders(entity);

  const {
    result: customProviders,
    loading: customProvidersLoading,
    refetch: refetchCustomProviders,
  } = useBaseObjectInstances('Provider', {
    project_id: projectId,
    filter: {
      latest_only: true,
    },
  });

  const {result: customProviderModels, loading: customProviderModelsLoading} =
    useBaseObjectInstances('ProviderModel', {
      project_id: projectId,
      filter: {
        latest_only: true,
      },
    });

  const {result: savedModels, loading: savedModelsLoading} =
    useLeafObjectInstances('LLMStructuredCompletionModel', {
      project_id: projectId,
    });

  const llmDropdownOptions = useLLMDropdownOptions(
    configuredProviders,
    configuredProvidersLoading,
    customProviders || [],
    customProviderModels || [],
    customProvidersLoading,
    savedModels || [],
    savedModelsLoading
  );

  const [model, setModel] = useState<string | undefined>(value);

  const {userInfo} = useViewerInfo();
  const {isAdmin: maybeTeamAdmin} = useIsTeamAdmin(
    entity,
    userInfo && 'username' in userInfo ? userInfo.username : ''
  );
  const isTeamAdmin = maybeTeamAdmin ?? false;

  return (
    <LLMDropdown
      value={model ?? ''}
      onChange={(
        model: string,
        maxTokens: number,
        savedModel?: SavedPlaygroundModelState
      ) => {
        setModel(model);
        if (savedModel) {
          onChange(model as LLMMaxTokensKey, maxTokens, savedModel);
        }
      }}
      entity={entity}
      project={project}
      isTeamAdmin={isTeamAdmin}
      refetchConfiguredProviders={refetchConfiguredProviders}
      refetchCustomLLMs={refetchCustomProviders}
      llmDropdownOptions={llmDropdownOptions}
      areProvidersLoading={
        configuredProvidersLoading ||
        customProvidersLoading ||
        customProviderModelsLoading ||
        savedModelsLoading ||
        (loading ?? false)
      }
      customProvidersResult={customProviders || []}
    />
  );
};
