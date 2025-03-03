import {useSecrets} from '@wandb/weave/common/hooks/useSecrets';

import {LLM_PROVIDER_SECRETS, LLM_PROVIDERS} from './llmMaxTokens';

const hasAllSecrets = (secrets: string[], providerKey: string[]) => {
  return providerKey.every(key => secrets.includes(key));
};

const missingSecrets = (secrets: string[], providerKey: string[]) => {
  return providerKey.filter(key => !secrets.includes(key)).join(', ');
};

export const useConfiguredProviders = (entityName: string) => {
  const {loading: secretsLoading, secrets} = useSecrets({entityName});

  const providers = LLM_PROVIDERS.reduce((acc, provider) => {
    acc[provider] = {
      status: hasAllSecrets(secrets, LLM_PROVIDER_SECRETS[provider]),
      missingSecrets: missingSecrets(secrets, LLM_PROVIDER_SECRETS[provider]),
    };
    return acc;
  }, {} as Record<string, {status: boolean; missingSecrets: string}>);

  return {
    result: secretsLoading ? {} : providers,
    loading: secretsLoading,
  };
};
