import {
  Secret,
  useTeamSecrets,
} from '@wandb/weave/common/hooks/useEntitySecrets';

import {LLM_PROVIDER_SECRETS, LLM_PROVIDERS} from './llmMaxTokens';

const hasAllSecrets = (secrets: Secret[], providerKey: string[]) => {
  return providerKey.every(key => secrets.some(secret => secret.name === key));
};

const missingSecrets = (secrets: Secret[], providerKey: string[]) => {
  return providerKey
    .filter(key => !secrets.some(secret => secret.name === key))
    .join(', ');
};

export const useConfiguredProviders = (entityName: string) => {
  const {loading: secretsLoading, secrets} = useTeamSecrets(entityName);

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
