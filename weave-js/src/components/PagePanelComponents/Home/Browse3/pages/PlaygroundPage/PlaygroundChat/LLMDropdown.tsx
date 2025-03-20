import {Box} from '@mui/material';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useState} from 'react';

import {AddProviderDrawer} from '../../OverviewPage/AddProviderDrawer';
import {useBaseObjectInstances} from '../../wfReactInterface/objectClassQuery';
import {
  LLM_MAX_TOKENS,
  LLM_PROVIDER_LABELS,
  LLMMaxTokensKey,
} from '../llmMaxTokens';
import {useConfiguredProviders} from '../useConfiguredProviders';
import {
  addProviderOption,
  CustomOption,
  dividerOption,
  ProviderOption,
} from './LLMDropdownOptions';

interface LLMDropdownProps {
  value: LLMMaxTokensKey;
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
  entity: string;
  project: string;
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({
  value,
  onChange,
  entity,
  project,
}) => {
  const [isAddProviderDrawerOpen, setIsAddProviderDrawerOpen] = useState(false);
  const {result: configuredProviders, loading: configuredProvidersLoading} =
    useConfiguredProviders(entity);

  const {
    result: customProvidersResult,
    loading: customProvidersLoading,
    refetch: refetchCustomProviders,
  } = useBaseObjectInstances('Provider', {
    project_id: `${entity}/${project}`,
    filter: {
      latest_only: true,
    },
  });

  const {
    result: customProviderModelsResult,
    loading: customProviderModelsLoading,
    refetch: refetchCustomProviderModels,
  } = useBaseObjectInstances('ProviderModel', {
    project_id: `${entity}/${project}`,
    filter: {
      latest_only: true,
    },
  });

  const customLoading = customProvidersLoading || customProviderModelsLoading;

  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const isTeamAdmin = !loadingUserInfo && userInfo?.roles[entity] === 'admin';


  const options: ProviderOption[] = [];
  const disabledOptions: ProviderOption[] = [];

  if (configuredProvidersLoading) {
    options.push({
      label: 'Loading providers...',
      value: 'loading',
      llms: [],
    });
  } else {
    Object.entries(configuredProviders).forEach(([provider, {status}]) => {
      const providerLLMs = Object.entries(LLM_MAX_TOKENS)
        .filter(([_, config]) => config.provider === provider)
        .map(([llmKey]) => ({
          label: llmKey,
          value: llmKey as LLMMaxTokensKey,
          max_tokens: LLM_MAX_TOKENS[llmKey as LLMMaxTokensKey].max_tokens,
        }));

      const option = {
        label:
          LLM_PROVIDER_LABELS[provider as keyof typeof LLM_PROVIDER_LABELS],
        value: provider,
        llms: status ? providerLLMs : [],
        isDisabled: !status,
      };

      if (!status) {
        disabledOptions.push(option);
      } else {
        options.push(option);
      }
    });
  }

  // Add custom providers
  if (!customLoading) {
    customProvidersResult?.forEach(provider => {
      const providerName = provider.val.name || '';
      const currentProviderModels =
        customProviderModelsResult?.filter(
          obj => obj.val.provider === provider.digest
        ) || [];

      const shortenedProviderLabel =
        providerName.length > 20
          ? providerName.slice(0, 2) + '...' + providerName.slice(-4)
          : providerName;

      const llmOptions = currentProviderModels.map(model => ({
        label: shortenedProviderLabel + '/' + model.val.name,
        value: (provider.val.name + '/' + model.val.name) as LLMMaxTokensKey,
        max_tokens: model.val.max_tokens,
      }));

      if (llmOptions.length > 0) {
        options.push({
          label: providerName,
          value: providerName,
          llms: llmOptions,
        });
      }
    });
  }

  // Combine enabled and disabled options
  // Add a divider option before the add provider option
  const allOptions = [
    ...options,
    ...disabledOptions,
    dividerOption,
    addProviderOption,
  ];

  const refetch = useCallback(() => {
    refetchCustomProviders();
    refetchCustomProviderModels();
  }, [refetchCustomProviders, refetchCustomProviderModels]);

  const handleCloseDrawer = () => {
    setIsAddProviderDrawerOpen(false);
  };

  return (
    <Box sx={{width: '300px'}}>
      <Select
        isDisabled={configuredProvidersLoading}
        placeholder={
          configuredProvidersLoading ? 'Loading providers...' : 'Select a model'
        }
        value={allOptions.find(
          option =>
            'llms' in option && option.llms?.some(llm => llm.value === value)
        )}
        formatOptionLabel={(option: ProviderOption, meta) => {
          if (meta.context === 'value' && 'llms' in option) {
            const selectedLLM = option.llms.find(llm => llm.value === value);
            return selectedLLM?.label ?? option.label;
          }
          return option.label;
        }}
        onChange={option => {
          // When you click a provider, select the first LLM
          if (option && 'value' in option) {
            const selectedOption = option as ProviderOption;

            // Check if the "Add AI provider" option was selected
            if (selectedOption.value === 'add-provider') {
              setIsAddProviderDrawerOpen(true);
              return;
            }

            if (selectedOption.llms.length > 0) {
              const llm = selectedOption.llms[0];
              onChange(llm.value, llm.max_tokens);
            }
          }
        }}
        options={allOptions}
        maxMenuHeight={500}
        components={{
          Option: props => (
            <CustomOption
              {...props}
              onChange={onChange}
              entity={entity}
              project={project}
              isAdmin={isTeamAdmin}
            />
          ),
        }}
        size="medium"
        isSearchable
        filterOption={(option, inputValue) => {
          const searchTerm = inputValue.toLowerCase();
          const label =
            typeof option.data.label === 'string' ? option.data.label : '';
          return (
            label.toLowerCase().includes(searchTerm) ||
            option.data.llms.some(llm =>
              llm.label.toLowerCase().includes(searchTerm)
            )
          );
        }}
      />

      <AddProviderDrawer
        isOpen={isAddProviderDrawerOpen}
        onClose={handleCloseDrawer}
        refetch={refetch}
        projectId={`${entity}/${project}`}
        providers={customProvidersResult?.map(p => p.val.name || '') || []}
      />
    </Box>
  );
};
