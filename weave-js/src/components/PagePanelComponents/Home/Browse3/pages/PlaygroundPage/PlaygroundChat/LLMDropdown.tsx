import {Box} from '@mui/material';
import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useEffect, useMemo, useState} from 'react';

import {AddProviderDrawer} from '../../OverviewPage/AddProviderDrawer';
import {Provider} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {OptionalSavedPlaygroundModelParams} from '../types';
import {CustomOption, LLMOption, ProviderOption} from './LLMDropdownOptions';
import {ProviderConfigDrawer} from './ProviderConfigDrawer';

interface LLMDropdownProps {
  value: LLMMaxTokensKey | string;
  onChange: (
    value: LLMMaxTokensKey | string,
    maxTokens: number,
    baseModel: LLMMaxTokensKey | null,
    params: OptionalSavedPlaygroundModelParams
  ) => void;
  entity: string;
  project: string;
  isTeamAdmin: boolean;
  allOptions: ProviderOption[];
  overallLoading: boolean;
  refetch: () => void;
  customProvidersResult: Provider[];
}

export const LLMDropdown: React.FC<LLMDropdownProps> = ({
  value,
  onChange,
  entity,
  project,
  isTeamAdmin,
  allOptions,
  overallLoading,
  refetch,
  customProvidersResult,
}) => {
  const [isAddProviderDrawerOpen, setIsAddProviderDrawerOpen] = useState(false);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);

  const handleCloseDrawer = () => {
    setIsAddProviderDrawerOpen(false);
    refetch();
  };

  const handleConfigureProvider = (provider: string) => {
    setSelectedProvider(provider);
    setConfigDrawerOpen(true);
  };

  const handleCloseConfigDrawer = useCallback(() => {
    setConfigDrawerOpen(false);
    setSelectedProvider(null);
    refetch();
  }, [refetch]);

  const isValueAvailable = useMemo(() => {
    return allOptions.some(
      (option: ProviderOption) =>
        'llms' in option && option.llms?.some(llm => llm && llm.value === value)
    );
  }, [allOptions, value]);

  useEffect(() => {
    if (!isValueAvailable && !overallLoading) {
      let firstAvailableLlm: LLMOption | null = null;
      for (const option of allOptions) {
        if ('llms' in option && !option.isDisabled && option.llms.length > 0) {
          firstAvailableLlm = option.llms[0];
          break;
        }
      }
      if (firstAvailableLlm) {
        onChange(
          firstAvailableLlm.value,
          firstAvailableLlm.max_tokens,
          firstAvailableLlm.baseModelId ?? null,
          firstAvailableLlm.defaultParams ?? {}
        );
      }
    }
  }, [isValueAvailable, allOptions, onChange, overallLoading]);

  return (
    <Box sx={{width: '300px'}}>
      <Select
        isDisabled={overallLoading}
        placeholder={overallLoading ? 'Loading models...' : 'Select a model'}
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
              if (llm) {
                onChange(
                  llm.value,
                  llm.max_tokens,
                  llm.baseModelId ?? null,
                  llm.defaultParams ?? {}
                );
              }
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
        refetch={refetch}
        projectId={`${entity}/${project}`}
        providers={customProvidersResult?.map(p => p.name || '') || []}
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
