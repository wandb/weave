import {useSecrets} from '@wandb/weave/common/hooks/useSecrets';

import {LLM_PROVIDER_SECRETS, LLM_PROVIDERS} from './llmMaxTokens';

const hasAllSecrets = (secrets: string[], providerKey: string[]): boolean => {
  return providerKey.every(key => secrets.includes(key));
};

const missingSecrets = (secrets: string[], providerKey: string[]): string => {
  return providerKey.filter(key => !secrets.includes(key)).join(', ');
};

type ProviderStatus = {
  status: boolean;
  missingSecrets: string;
};

export const useConfiguredProviders = (
  entityName: string
): {
  result: Record<string, ProviderStatus>;
  loading: boolean;
  refetch: () => void;
} => {
  const {loading: secretsLoading, secrets, refetch} = useSecrets({entityName});

  const providers = LLM_PROVIDERS.reduce((acc, provider) => {
    acc[provider] = {
      status: hasAllSecrets(secrets, LLM_PROVIDER_SECRETS[provider]),
      missingSecrets: missingSecrets(secrets, LLM_PROVIDER_SECRETS[provider]),
    };
    return acc;
  }, {} as Record<string, ProviderStatus>);

  return {
    result: secretsLoading ? {} : providers,
    loading: secretsLoading,
    refetch,
  };
};
