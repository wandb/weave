import {useCallback, useMemo} from 'react';

import {
  LlmStructuredCompletionModel,
  LlmStructuredCompletionModelDefaultParams,
} from '../../wfReactInterface/generatedBuiltinObjectClasses.zod';
import {useBaseObjectInstances} from '../../wfReactInterface/objectClassQuery';
import {
  findMaxTokensByModelName,
  LLM_MAX_TOKENS,
  LLM_PROVIDER_LABELS,
  LLMMaxTokensKey,
} from '../llmMaxTokens';
import {
  OptionalSavedPlaygroundModelParams,
  PlaygroundResponseFormats,
} from '../types';
import {useConfiguredProviders} from '../useConfiguredProviders';
import {
  addProviderOption,
  dividerOption,
  LLMOption,
  ProviderOption,
} from './LLMDropdownOptions';

type UseLLMDropdownOptionsParams = {
  entity: string;
  project: string;
};

export function useLLMDropdownOptions({
  entity,
  project,
}: UseLLMDropdownOptionsParams) {
  const projectId = `${entity}/${project}`;

  // Fetch configured providers (OpenAI, Anthropic, etc.)
  const {
    result: configuredProviders,
    loading: configuredProvidersLoading,
    refetch: refetchConfiguredProviders,
  } = useConfiguredProviders(entity);

  // Fetch custom providers added by the user
  const {
    result: customProvidersResult,
    loading: customProvidersLoading,
    refetch: refetchCustomProviders,
  } = useBaseObjectInstances('Provider', {
    project_id: projectId,
    filter: {latest_only: true},
  });

  // Fetch custom provider models (specific models for custom providers)
  const {
    result: customProviderModelsResult,
    loading: customProviderModelsLoading,
    refetch: refetchCustomProviderModels,
  } = useBaseObjectInstances('ProviderModel', {
    project_id: projectId,
    filter: {latest_only: true},
  });

  // Fetch saved model configurations
  const {
    result: savedModelsResult,
    loading: savedModelsLoading,
    refetch: refetchSavedModels,
  } = useBaseObjectInstances('LLMStructuredCompletionModel', {
    project_id: projectId,
    filter: {latest_only: true},
  });

  // Calculate aggregate loading states
  const customLoading =
    customProvidersLoading || customProviderModelsLoading || savedModelsLoading;
  const overallLoading = configuredProvidersLoading || customLoading;

  // Process saved models into a provider-organized structure
  const savedModelsByProvider = useMemo(() => {
    const lookup: Record<string, LLMOption[]> = {};

    if (savedModelsResult) {
      savedModelsResult.forEach(savedModelObj => {
        const savedModelVal = savedModelObj.val as LlmStructuredCompletionModel;
        const baseModelId = savedModelVal.llm_model_id;
        const savedModelName =
          savedModelVal.name ?? savedModelObj.object_id ?? 'Unnamed Model';

        let provider: string | undefined;
        let maxTokens: number | undefined;

        // Try to determine provider from built-in model list
        if (baseModelId in LLM_MAX_TOKENS) {
          const baseModelConfig =
            LLM_MAX_TOKENS[baseModelId as LLMMaxTokensKey];
          provider = baseModelConfig.provider;
          maxTokens = baseModelConfig.max_tokens;
        } else {
          // Try to determine from custom provider models
          const customModelMatch = customProviderModelsResult?.find(
            customModel => {
              const customProviderMatch = customProvidersResult?.find(
                p => p.digest === customModel.val.provider
              );
              return (
                `${customProviderMatch?.val.name}/${customModel.val.name}` ===
                baseModelId
              );
            }
          );

          if (customModelMatch) {
            const customProviderMatch = customProvidersResult?.find(
              p => p.digest === customModelMatch.val.provider
            );
            provider = customProviderMatch?.val.name ?? undefined;
            maxTokens = customModelMatch.val.max_tokens;
          }
        }

        // Fallback max tokens determination
        if (maxTokens === undefined) {
          maxTokens = findMaxTokensByModelName(baseModelId);
        }

        // Add model to the provider's list if we identified a provider
        if (provider && maxTokens !== undefined) {
          if (!lookup[provider]) {
            lookup[provider] = [];
          }
          lookup[provider].push({
            label: savedModelName,
            value: savedModelName,
            baseModelId: baseModelId as LLMMaxTokensKey,
            max_tokens: maxTokens,
            defaultParams: convertDefaultParamsToOptionalPlaygroundModelParams(
              savedModelVal.default_params ?? {},
              savedModelVal.messages_template ?? []
            ),
          });
        }
      });
    }

    // Sort models alphabetically within each provider
    Object.values(lookup).forEach(models =>
      models.sort((a, b) => a.label.localeCompare(b.label))
    );

    return lookup;
  }, [savedModelsResult, customProviderModelsResult, customProvidersResult]);

  // Build the final dropdown options structure
  const allOptions = useMemo(() => {
    const options: ProviderOption[] = [];
    const disabledOptions: ProviderOption[] = [];

    // Process built-in providers
    if (!configuredProvidersLoading) {
      Object.entries(configuredProviders).forEach(([provider, {status}]) => {
        const savedProviderModels = savedModelsByProvider[provider] || [];

        const providerLLMs = Object.entries(LLM_MAX_TOKENS)
          .filter(([_, config]) => config.provider === provider)
          .map(
            ([llmKey, config]): LLMOption => ({
              label: llmKey,
              value: llmKey as LLMMaxTokensKey,
              max_tokens: config.max_tokens,
            })
          );

        // Combine saved models with built-in models for this provider
        const allLLMsForProvider = [...savedProviderModels, ...providerLLMs];

        const option: ProviderOption = {
          label:
            LLM_PROVIDER_LABELS[provider as keyof typeof LLM_PROVIDER_LABELS],
          value: provider,
          llms: status ? allLLMsForProvider : [],
          isDisabled: !status,
        };

        // Separate enabled and disabled providers
        if (!status) {
          disabledOptions.push(option);
        } else {
          options.push(option);
        }
      });
    }

    // Process custom providers
    if (!customLoading) {
      customProvidersResult?.forEach(provider => {
        const providerName = provider.val.name || '';
        const providerKey = providerName;

        const savedCustomProviderModels =
          savedModelsByProvider[providerKey] || [];

        const currentProviderModels =
          customProviderModelsResult?.filter(
            obj => obj.val.provider === provider.digest
          ) || [];

        const shortenedProviderLabel =
          providerName.length > 20
            ? providerName.slice(0, 2) + '...' + providerName.slice(-4)
            : providerName;

        const llmOptions: LLMOption[] = currentProviderModels.map(model => ({
          label: `${shortenedProviderLabel}/${model.val.name}`,
          value: `${providerName}/${model.val.name}` as LLMMaxTokensKey,
          max_tokens: model.val.max_tokens,
        }));

        const allLLMsForCustomProvider = [
          ...savedCustomProviderModels,
          ...llmOptions,
        ];

        if (allLLMsForCustomProvider.length > 0) {
          options.push({
            label: providerName,
            value: providerName,
            llms: allLLMsForCustomProvider,
          });
        }
      });
    }

    // Return all options with divider and add-provider button at the end
    return [...options, ...disabledOptions, dividerOption, addProviderOption];
  }, [
    configuredProvidersLoading,
    configuredProviders,
    customLoading,
    customProvidersResult,
    customProviderModelsResult,
    savedModelsByProvider,
  ]);

  // Combined refetch function
  const refetch = useCallback(() => {
    refetchConfiguredProviders();
    refetchCustomProviders();
    refetchCustomProviderModels();
    refetchSavedModels();
  }, [
    refetchConfiguredProviders,
    refetchCustomProviders,
    refetchCustomProviderModels,
    refetchSavedModels,
  ]);

  return {
    // Main processed data
    allOptions,
    savedModelsByProvider,

    // Loading states
    overallLoading,
    customLoading,
    configuredProvidersLoading,
    customProvidersLoading,
    customProviderModelsLoading,
    savedModelsLoading,

    // Query results
    configuredProviders,
    customProvidersResult,
    customProviderModelsResult,
    savedModelsResult,

    // Refetch functions
    refetch,
    refetchConfiguredProviders,
    refetchCustomProviders,
    refetchCustomProviderModels,
    refetchSavedModels,
  };
}

// Helper function to convert saved model parameters to playground format
const convertDefaultParamsToOptionalPlaygroundModelParams = (
  defaultParams: LlmStructuredCompletionModelDefaultParams | null | undefined,
  messagesTemplate: Record<string, string>[] | null | undefined
): OptionalSavedPlaygroundModelParams => {
  if (!defaultParams) return {};

  // Helper function to convert null or undefined to undefined
  const nullToUndefined = <T>(value: T | null | undefined): T | undefined => {
    return value === null || value === undefined ? undefined : value;
  };

  return {
    temperature: nullToUndefined(defaultParams.temperature),
    topP: nullToUndefined(defaultParams.top_p),
    maxTokens: nullToUndefined(defaultParams.max_tokens),
    frequencyPenalty: nullToUndefined(defaultParams.frequency_penalty),
    presencePenalty: nullToUndefined(defaultParams.presence_penalty),
    nTimes: nullToUndefined(defaultParams.n_times) ?? 1,
    responseFormat: nullToUndefined(
      defaultParams.response_format as PlaygroundResponseFormats
    ),
    functions: nullToUndefined(defaultParams.functions),
    stopSequences: nullToUndefined(defaultParams.stop),
    messagesTemplate: nullToUndefined(messagesTemplate),
  };
};
