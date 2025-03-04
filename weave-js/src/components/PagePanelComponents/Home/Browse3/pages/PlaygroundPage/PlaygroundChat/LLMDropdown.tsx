import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
import React from 'react';

import {AddProviderDrawer} from '../../OverviewPage/AddProviderDrawer';
import {useWFHooks} from '../../wfReactInterface/context';
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

const CUSTOM_PROVIDER_PREFIX = '__weave_custom_provider__/';

export const LLMDropdown: React.FC<LLMDropdownProps> = ({
  value,
  onChange,
  entity,
  project,
}) => {
  const {result: configuredProviders, loading: configuredProvidersLoading} =
    useConfiguredProviders(entity);

  const {useRootObjectVersions} = useWFHooks();
  const {result: objectsRes, loading: objectsLoading} = useRootObjectVersions(
    entity,
    project,
    {
      latestOnly: true,
      baseObjectClasses: ['Provider', 'ProviderModel', 'LLMModel'],
    }
  );

  const providers =
    objectsRes?.filter(obj => obj.baseObjectClass === 'Provider') || [];

  const providerModels =
    objectsRes?.filter(obj => obj.baseObjectClass === 'ProviderModel') || [];

  const llmModels =
    objectsRes?.filter(obj => obj.baseObjectClass === 'LLMModel') || [];

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
  if (!objectsLoading) {
    providers.forEach(provider => {
      const currentProviderModels = providerModels?.filter(
        obj => obj.val.provider === provider.versionHash
      );

      const currentLLMModels = llmModels?.filter(obj =>
        currentProviderModels.some(
          pm => pm.versionHash === obj.val.provider_model
        )
      );

      const shortenedProviderLabel =
        provider.val.name.length > 20
          ? provider.val.name.slice(0, 2) + '...' + provider.val.name.slice(-4)
          : provider.val.name;

      const customLLMs = [
        ...currentProviderModels.map(model => ({
          label: shortenedProviderLabel + '/' + model.val.name,
          value: (CUSTOM_PROVIDER_PREFIX +
            provider.val.name +
            '/' +
            model.val.name) as LLMMaxTokensKey,
          max_tokens: model.val.max_tokens,
        })),
        ...currentLLMModels.map(model => ({
          label: shortenedProviderLabel + '/' + model.val.name,
          value: (CUSTOM_PROVIDER_PREFIX +
            provider.val.name +
            '/' +
            model.val.name) as LLMMaxTokensKey,
          max_tokens: model.val.max_tokens,
        })),
      ];

      options.push({
        label: provider.val.name,
        value: provider.val.name,
        llms: customLLMs,
      });
    });
  }

  // Combine enabled and disabled options
  // Add a divider option before the add provider option
  const allOptions = [
    ...options,
    ...disabledOptions,
    dividerOption,
    // TODO: make this open drawer
    addProviderOption,
  ];

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
      {/* TODO: make this draewer work */}
      {/* Add editing to porivders? */}
      {/* Or just make the add provider option just add a link */}
      {/* <AddProviderDrawer 
  isOpen,
  onClose,
  refetch,
  providers,
  editingProvider, /> */}
    </Box>
  );
};
