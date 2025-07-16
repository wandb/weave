import {Select} from '@wandb/weave/components/Form/Select';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {useEntityProject} from '../../../context';
import {INFERENCE_PATH} from '../../../inference/util';
import {AddProviderDrawer} from '../../OverviewPage/AddProviderDrawer';
import {
  TraceObjSchemaForBaseObjectClass,
  useBaseObjectInstances,
  useLeafObjectInstances,
} from '../../wfReactInterface/objectClassQuery';
import {LLMMaxTokensKey} from '../llmMaxTokens';
import {SavedPlaygroundModelState} from '../types';
import {useConfiguredProviders} from '../useConfiguredProviders';
import {
  CustomOption,
  LLMOption,
  LLMOptionToSavedPlaygroundModelState,
  OpenDirection,
  ProviderOption,
  SAVED_MODEL_OPTION_VALUE,
  useLLMDropdownOptions,
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
  selectFirstAvailable?: boolean;
  direction: OpenDirection;
  className?: string;
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
  selectFirstAvailable,
  direction,
  className,
}) => {
  const [isAddProviderDrawerOpen, setIsAddProviderDrawerOpen] = useState(false);
  const [configDrawerOpen, setConfigDrawerOpen] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [menuPlacement, setMenuPlacement] = useState<'top' | 'bottom' | 'auto'>(
    'auto'
  );
  const selectRef = useRef<HTMLDivElement>(null);

  // TOOD: Avoid direct url manipulation
  const history = useHistory();
  const handleViewCatalog = (path?: string) => {
    const prefixedPath = path ? `${INFERENCE_PATH}/${path}` : INFERENCE_PATH;
    history.push(prefixedPath);
  };

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
    if (!isValueAvailable && !areProvidersLoading && selectFirstAvailable) {
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
    selectFirstAvailable,
  ]);

  const handleMenuOpen = () => {
    if (selectRef.current) {
      const rect = selectRef.current.getBoundingClientRect();
      const dropdownMidpoint = (rect.top + rect.bottom) / 2;
      const viewportMidpoint = window.innerHeight / 2;

      // If dropdown is above 50% of viewport, open down; if below, open up
      setMenuPlacement(dropdownMidpoint < viewportMidpoint ? 'bottom' : 'top');
    }
  };

  return (
    <div className={className} ref={selectRef}>
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
        menuPlacement={menuPlacement}
        onMenuOpen={handleMenuOpen}
        components={{
          Option: props => (
            <CustomOption
              {...props}
              onChange={onChange}
              entity={entity}
              project={project}
              isAdmin={isTeamAdmin}
              onConfigureProvider={handleConfigureProvider}
              onViewCatalog={handleViewCatalog}
              direction={direction}
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
    </div>
  );
};

interface LLMDropdownLoadedProps {
  value: LLMMaxTokensKey | string;
  onChange: (
    value: LLMMaxTokensKey | string,
    maxTokens: number,
    savedModel?: SavedPlaygroundModelState
  ) => void;
  isTeamAdmin: boolean;
  className?: string;
  direction: OpenDirection;
  selectFirstAvailable?: boolean;
  excludeSavedModels?: boolean;
}

export const LLMDropdownLoaded: React.FC<LLMDropdownLoadedProps> = ({
  value,
  onChange,
  isTeamAdmin,
  className,
  direction,
  selectFirstAvailable = false,
  excludeSavedModels = false,
}) => {
  const {entity, project, projectId} = useEntityProject();

  const {
    result: configuredProviders,
    loading: configuredProvidersLoading,
    refetch: refetchConfiguredProviders,
  } = useConfiguredProviders(entity);

  const {
    result: customProvidersResult,
    loading: customProvidersLoading,
    refetch: refetchCustomProviders,
  } = useBaseObjectInstances('Provider', {
    project_id: projectId,
    filter: {
      latest_only: true,
    },
  });

  const {
    result: customProviderModelsResult,
    loading: customProviderModelsLoading,
    refetch: refetchCustomProviderModels,
  } = useBaseObjectInstances('ProviderModel', {
    project_id: projectId,
    filter: {
      latest_only: true,
    },
  });

  const {result: savedModelsResult, loading: savedModelsLoading} =
    useLeafObjectInstances(
      'LLMStructuredCompletionModel',
      {
        project_id: projectId,
      },
      !excludeSavedModels
    );

  const refetchCustomLLMs = useCallback(() => {
    refetchCustomProviders();
    refetchCustomProviderModels();
  }, [refetchCustomProviders, refetchCustomProviderModels]);

  const llmDropdownOptions = useLLMDropdownOptions(
    configuredProviders,
    configuredProvidersLoading,
    customProvidersResult || [],
    customProviderModelsResult || [],
    customProvidersLoading,
    excludeSavedModels ? [] : savedModelsResult || [],
    excludeSavedModels ? false : savedModelsLoading
  );

  const areCustomProvidersLoading =
    customProvidersLoading || customProviderModelsLoading;

  const areProvidersLoading =
    configuredProvidersLoading || areCustomProvidersLoading;

  return (
    <LLMDropdown
      value={value}
      onChange={onChange}
      isTeamAdmin={isTeamAdmin}
      direction={direction}
      selectFirstAvailable={selectFirstAvailable}
      entity={entity}
      project={project}
      refetchConfiguredProviders={refetchConfiguredProviders}
      refetchCustomLLMs={refetchCustomLLMs}
      llmDropdownOptions={llmDropdownOptions}
      areProvidersLoading={areProvidersLoading}
      customProvidersResult={customProvidersResult || []}
      className={className}
    />
  );
};
