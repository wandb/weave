import {toast} from '@wandb/weave/common/components/elements/Toast';
import {useCallback, useMemo} from 'react';

import {useWFHooks} from '../wfReactInterface/context';
import {useBaseObjectInstances} from '../wfReactInterface/objectClassQuery';

interface CustomProvider {
  id: string;
  name: string | null | undefined;
  baseUrl: string;
  apiKeyName: string;
  description: string | null | undefined;
  returnType: string | undefined;
  extraHeaders: Array<[string, string]>;
  lastUpdated: string;
  providerModels: any[];
  models: number;
  delete: () => void;
  edit: () => void;
}

interface EditingProvider {
  name: string | null | undefined;
  baseUrl: string;
  apiKey: string;
  models: Array<string | null | undefined>;
  headers: Array<[string, string]>;
  maxTokens: number[];
}

interface UseCustomProvidersProps {
  entityName: string;
  projectName: string;
  setEditingProvider: (provider: EditingProvider | null) => void;
  setIsDrawerOpen: (isOpen: boolean) => void;
  setDeletingProvider: (
    provider: {
      name: string | null | undefined;
      deleteAction: () => Promise<void>;
    } | null
  ) => void;
}

export const useCustomProviders = ({
  entityName,
  projectName,
  setEditingProvider,
  setIsDrawerOpen,
  setDeletingProvider,
}: UseCustomProvidersProps) => {
  // Get object delete function
  const {useObjectDeleteFunc} = useWFHooks();
  const {objectDeleteAllVersions} = useObjectDeleteFunc();

  // Fetch custom providers
  const {
    result: customProvidersResult,
    loading: customProvidersLoading,
    refetch: refetchCustomProviders,
  } = useBaseObjectInstances('Provider', {
    project_id: `${entityName}/${projectName}`,
    filter: {
      latest_only: true,
    },
  });

  // Fetch custom provider models
  const {
    result: customProviderModelsResult,
    loading: customProviderModelsLoading,
    refetch: refetchCustomProviderModels,
  } = useBaseObjectInstances('ProviderModel', {
    project_id: `${entityName}/${projectName}`,
    filter: {
      latest_only: true,
    },
  });

  // Function to refetch both providers and provider models
  const refetch = useCallback(() => {
    refetchCustomProviders();
    refetchCustomProviderModels();
  }, [refetchCustomProviders, refetchCustomProviderModels]);

  // Format custom providers with their associated models
  const customProviders: CustomProvider[] = useMemo(
    () =>
      customProvidersResult?.map(provider => {
        const providerModels =
          customProviderModelsResult?.filter(
            model => model.val.provider === provider.digest
          ) || [];

        return {
          id: provider.digest,
          name: provider.val.name,
          baseUrl: provider.val.base_url,
          apiKeyName: provider.val.api_key_name,
          description: provider.val.description,
          returnType: provider.val.return_type,
          extraHeaders: Object.entries(provider.val.extra_headers || {}) || [],
          lastUpdated: provider.created_at,
          providerModels,
          models: providerModels.length,
          delete: () => {
            setDeletingProvider({
              name: provider.val.name,
              deleteAction: async () => {
                setDeletingProvider(null);

                try {
                  await objectDeleteAllVersions({
                    entity: entityName,
                    project: projectName,
                    objectId: provider.val.name || '',
                    weaveKind: 'object',
                    scheme: 'weave',
                    versionHash: '',
                    path: '',
                  });
                  // Delete all related models in parallel
                  await Promise.all([
                    ...providerModels.map(model =>
                      objectDeleteAllVersions({
                        entity: entityName,
                        project: projectName,
                        objectId: `${provider.val.name || ''}-${
                          model.val.name || ''
                        }`,
                        weaveKind: 'object',
                        scheme: 'weave',
                        versionHash: '',
                        path: '',
                      })
                    ),
                  ]);

                  refetch();
                  toast(`Provider "${provider.val.name}" deleted`, {
                    type: 'success',
                  });
                } catch (error) {
                  console.error('Error deleting provider:', error);
                  toast('Error deleting provider', {
                    type: 'error',
                  });
                }
              },
            });
          },
          edit: () => {
            setEditingProvider({
              name: provider.val.name,
              baseUrl: provider.val.base_url,
              apiKey: provider.val.api_key_name,
              models: providerModels.map(model => model.val.name),
              headers: Object.entries(provider.val.extra_headers || {}),
              maxTokens: providerModels.map(model => model.val.max_tokens),
            });
            setIsDrawerOpen(true);
          },
        };
      }) || [],
    [
      customProvidersResult,
      customProviderModelsResult,
      entityName,
      projectName,
      objectDeleteAllVersions,
      refetch,
      setDeletingProvider,
      setEditingProvider,
      setIsDrawerOpen,
    ]
  );

  return {
    customProviders,
    customProvidersLoading:
      customProvidersLoading || customProviderModelsLoading,
    refetch,
  };
};
