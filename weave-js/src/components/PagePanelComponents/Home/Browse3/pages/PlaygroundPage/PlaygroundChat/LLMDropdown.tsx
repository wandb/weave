import {Box} from '@mui/material';
import {useOrgName} from '@wandb/weave/common/hooks/useOrganization';
import {useViewerUserInfo2} from '@wandb/weave/common/hooks/useViewerUserInfo';
import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useEffect, useState} from 'react';

import * as userEvents from '../../../../../../../integrations/analytics/userEvents';
import {AddProviderDrawer} from '../../OverviewPage/AddProviderDrawer';
import {TraceObjSchemaForBaseObjectClass} from '../../wfReactInterface/objectClassQuery';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {CustomOption, ProviderOption} from './LLMDropdownOptions';
import {ProviderConfigDrawer} from './ProviderConfigDrawer';

interface LLMDropdownProps {
  value: LLMMaxTokensKey;
  onChange: (value: LLMMaxTokensKey, maxTokens: number) => void;
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

  const {loading: viewerLoading, userInfo} = useViewerUserInfo2();
  const userInfoLoaded = !viewerLoading ? userInfo : null;
  const {orgName} = useOrgName({
    entityName: entity,
    skip: viewerLoading || !entity,
  });

  const handleCloseDrawer = () => {
    setIsAddProviderDrawerOpen(false);
    refetchConfiguredProviders();
  };

  const handleConfigureProvider = (provider: string) => {
    if (!userInfoLoaded || !entity || !project) {
      return;
    }

    if (provider === 'custom-provider') {
      setIsAddProviderDrawerOpen(true);
      return;
    }

    userEvents.openConfigureProviderDrawer({
      userId: userInfoLoaded.id,
      organizationName: orgName,
      entityName: entity,
      projectName: project,
      source: 'llm_dropdown',
      provider,
    });

    setSelectedProvider(provider);
    setConfigDrawerOpen(true);
  };

  const handleCloseConfigDrawer = useCallback(() => {
    setConfigDrawerOpen(false);
    setSelectedProvider(null);
    refetchConfiguredProviders();
  }, [refetchConfiguredProviders]);

  const isValueAvailable = llmDropdownOptions.find(
    option =>
      'llms' in option && option.llms?.some(llm => llm && llm.value === value)
  );

  useEffect(() => {
    if (!isValueAvailable && !areProvidersLoading) {
      for (const option of llmDropdownOptions) {
        for (const llm of option.llms) {
          if (llm && llm.value && llm.max_tokens) {
            onChange(llm.value, llm.max_tokens);
            break;
          }
        }
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
          project={project}
          defaultProvider={selectedProvider}
        />
      )}
    </Box>
  );
};
