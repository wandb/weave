import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {AddProviderDrawer} from '../../OverviewPage/AddProviderDrawer';
import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {SavedPlaygroundModelState} from '../types';
import {
  CustomOption,
  LLMOption,
  LLMOptionToSavedPlaygroundModelState,
  ProviderOption,
  SAVED_MODEL_OPTION_VALUE,
} from './LLMDropdownOptions';
import {ProviderConfigDrawer} from './ProviderConfigDrawer';
interface LLMDropdownProps {
  value: LLMMaxTokensKey | string;
  onChange: (
    value: LLMMaxTokensKey | string,
    maxTokens: number,
    savedModel?: SavedPlaygroundModelState
  ) => void;
  entity: string;
  project: string;
  isTeamAdmin: boolean;
  refetchConfiguredProviders: () => void;
  refetchCustomLLMs: () => void;
  llmDropdownOptions: ProviderOption[];
  areProvidersLoading: boolean;
  customProvidersResult: TraceObjSchemaForBaseObjectClass<'Provider'>[];
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({
  value,
  onChange,
  entity,
  project,
  isTeamAdmin,
  refetchConfiguredProviders,
  refetchCustomLLMs,
  llmDropdownOptions,
  areProvidersLoading,
  customProvidersResult,
}) => {
  const [isAddProviderDrawerOpen, setIsAddProviderDrawerOpen] = useState(false);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  const handleCloseDrawer = () => {
    setIsAddProviderDrawerOpen(false);
    refetchConfiguredProviders();
  };

  const handleConfigureProvider = (provider: string) => {
    if (provider === 'custom-provider') {
      setIsAddProviderDrawerOpen(true);
      return;
    }
    setSelectedProvider(provider);
    setConfigDrawerOpen(true);
  };

  const handleCloseConfigDrawer = useCallback(() => {
    setConfigDrawerOpen(false);
    setSelectedProvider(null);
    refetchConfiguredProviders();
  }, [refetchConfiguredProviders]);

  const isValueAvailable = useMemo(
    () =>
      llmDropdownOptions.some(
        (option: ProviderOption) =>
          'llms' in option &&
          option.llms?.some(llm => llm && llm.value === value)
      ),
    [llmDropdownOptions, value]
  );

  useEffect(() => {
    if (!isValueAvailable && !areProvidersLoading) {
      let firstAvailableLlm: LLMOption | null = null;

      // Check if the value is a saved model
      const savedModelOption = llmDropdownOptions.find(
        option => option.value === SAVED_MODEL_OPTION_VALUE
      );
      if (savedModelOption) {
        firstAvailableLlm =
          savedModelOption.llms.find(
            llm => llm.objectId === value && llm.isLatest
          ) ?? null;
      }

      // If the value is not a saved model, check if theres any available LLM
      if (!firstAvailableLlm) {
        for (const option of llmDropdownOptions) {
          if (
            'llms' in option &&
            !option.isDisabled &&
            option.llms.length > 0
          ) {
            firstAvailableLlm = option.llms[0];
            break;
          }
        }
      }
      if (firstAvailableLlm) {
        onChange(
          firstAvailableLlm.value,
          firstAvailableLlm.max_tokens,
          LLMOptionToSavedPlaygroundModelState(firstAvailableLlm)
        );
      }
    }
  }, [
    isValueAvailable,
    llmDropdownOptions,
    onChange,
    value,
    areProvidersLoading,
  ]);

  return (
    <Box sx={{width: '300px'}}>
      <Select
        isDisabled={areProvidersLoading}
        placeholder={
          areProvidersLoading ? 'Loading providers...' : 'Select a model'
        }
        value={llmDropdownOptions.find(
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
            if (selectedOption.value === 'configure-provider') {
              setIsAddProviderDrawerOpen(true);
              return;
            }

            if (selectedOption.llms.length > 0) {
              const llm = selectedOption.llms[0];
              onChange(llm.value, llm.max_tokens);
            }
          }
        }}
        options={llmDropdownOptions}
        maxMenuHeight={500}
        components={{
          Option: props => (
            <CustomOption
              {...props}
              onChange={onChange}
              entity={entity}
              project={project}
              isAdmin={isTeamAdmin}
              onConfigureProvider={handleConfigureProvider}
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
        entityName={entity}
        projectName={project}
        isOpen={isAddProviderDrawerOpen}
        onClose={handleCloseDrawer}
        refetch={refetchCustomLLMs}
        projectId={`${entity}/${project}`}
        providers={customProvidersResult?.map(p => p.val.name || '') || []}
      />

      {configDrawerOpen && selectedProvider && (
        <ProviderConfigDrawer
          isOpen={configDrawerOpen}
          onClose={handleCloseConfigDrawer}
          entity={entity}
          defaultProvider={selectedProvider}
        />
      )}
    </Box>
  );
};
