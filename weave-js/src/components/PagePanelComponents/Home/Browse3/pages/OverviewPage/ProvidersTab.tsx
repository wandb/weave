import {ApolloProvider} from '@apollo/client';
import {GridColDef, GridRenderCellParams} from '@mui/x-data-grid-pro';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Icon} from '@wandb/weave/components/Icon';
import {Pill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useMemo} from 'react';

import {Link} from '../common/Links';
import {useConfiguredProviders} from '../PlaygroundPage/useConfiguredProviders';
import {useWFHooks, WFDataModelAutoProvider} from '../wfReactInterface/context';
import {Button} from '@wandb/weave/components/Button';
import {Timestamp} from '@wandb/weave/components/Timestamp';

import {DeleteModal} from '../common/DeleteModal';
import {useBaseObjectInstances} from '../wfReactInterface/objectClassQuery';
import {AddProviderDrawer} from './AddProviderDrawer';
import {ProviderTable} from './ProviderTable';

const ProviderStatus = ({isActive}: {isActive: boolean}) => {
  return (
    <div className="flex items-center">
      <Pill
        color={isActive ? 'green' : 'moon'}
        label={isActive ? 'Configured' : 'Not configured'}
        icon={isActive ? 'checkmark-circle' : 'failed'}
      />
    </div>
  );
};

const columns: GridColDef[] = [
  {
    field: 'name',
    headerName: 'NAME',
    flex: 0.2,
    minWidth: 200,
  },
  {
    field: 'status',
    headerName: 'STATUS',
    flex: 0.2,
    minWidth: 200,
    renderCell: (params: GridRenderCellParams) => (
      <div className="flex h-full items-center">
        <ProviderStatus isActive={params.value} />
      </div>
    ),
  },
  {
    field: 'missingSecrets',
    headerName: 'Missing Secrets',
    flex: 0.4,
    minWidth: 200,
    renderCell: (params: GridRenderCellParams) => (
      <div className="flex h-full items-center justify-between">
        <span className="text-moon-500">{params.value || 'None'}</span>
        {params.row.isAdmin && (
          <Link
            to={`/${params.row.entityName}/settings`}
            $variant="secondary"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2">
            {'Add team secret'}
            <Icon name="forward-next" />
          </Link>
        )}
      </div>
    ),
  },
];

const customColumns: GridColDef[] = [
  {
    field: 'name',
    headerName: 'NAME',
    flex: 0.25,
    minWidth: 200,
  },
  {
    field: 'models',
    headerName: 'MODELS',
    flex: 0.25,
    minWidth: 200,
  },
  {
    field: 'lastUpdated',
    headerName: 'LAST UPDATED',
    flex: 0.5,
    minWidth: 200,
    renderCell: (params: GridRenderCellParams) => (
      <div className="flex h-full items-center justify-between">
        <Timestamp value={params.value} format="relative" />
        <div className="flex h-full items-center justify-end">
          <Button
            variant="ghost"
            icon="pencil-edit"
            onClick={() => {
              params.row.edit();
            }}
          />
          <Button
            variant="ghost"
            icon="delete"
            onClick={() => {
              params.row.delete();
            }}
          />
        </div>
      </div>
    ),
  },
];

export const ProvidersTabInner: React.FC<{
  entityName?: string;
  projectName?: string;
}> = ({entityName = '', projectName = ''}) => {
  const {useObjectDeleteFunc} = useWFHooks();
  const {objectDeleteAllVersions} = useObjectDeleteFunc();

  const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);
  const [editingProvider, setEditingProvider] = React.useState<any>(null);
  const [deletingProvider, setDeletingProvider] = React.useState<any>(null);
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const isAdmin = !loadingUserInfo && userInfo?.admin;

  const {result: configuredProviders, loading: configuredProvidersLoading} =
    useConfiguredProviders(entityName);

  const providers = Object.entries(configuredProviders).map(
    ([provider, {status, missingSecrets}]) => ({
      id: provider,
      name: provider,
      status,
      missingSecrets,
      isAdmin,
      entityName,
    })
  );

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

  const {
    result: customModelsResult,
    loading: customModelsLoading,
    refetch: refetchCustomModels,
  } = useBaseObjectInstances('LLMModel', {
    project_id: `${entityName}/${projectName}`,
    filter: {
      latest_only: true,
    },
  });

  const getModels = (providerModels: any[], llmModels: any[]) => {
    const filteredLlmModels = llmModels.filter(llmModel =>
      providerModels.some(
        providerModel => providerModel.digest === llmModel.val.provider_model
      )
    );

    const noLLLMModelProviderModels = providerModels.filter(
      providerModel =>
        !filteredLlmModels.some(
          llmModel => llmModel.digest === providerModel.digest
        )
    );

    return {
      llmModels: filteredLlmModels,
      modelCount: filteredLlmModels.length + noLLLMModelProviderModels.length,
    };
  };

  const customProviders: any[] = useMemo(
    () =>
      customProvidersResult?.map(provider => {
        const providerModels =
          customProviderModelsResult?.filter(
            model => model.val.provider === provider.digest
          ) || [];

        const {llmModels, modelCount} = getModels(
          providerModels,
          customModelsResult || []
        );

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
          llmModels,
          models: modelCount,
          delete: () => {
            setDeletingProvider({
              name: provider.val.name,
              deleteAction: async () => {
                setDeletingProvider(null);
                await objectDeleteAllVersions({
                  entity: entityName,
                  project: projectName,
                  objectId: provider.val.name,
                  weaveKind: 'object',
                  scheme: 'weave',
                  versionHash: '',
                  path: '',
                });

                await Promise.all(
                  providerModels.map(model =>
                    objectDeleteAllVersions({
                      entity: entityName,
                      project: projectName,
                      objectId: model.val.name,
                      weaveKind: 'object',
                      scheme: 'weave',
                      versionHash: '',
                      path: '',
                    })
                  )
                );

                await Promise.all(
                  llmModels.map(model =>
                    objectDeleteAllVersions({
                      entity: entityName,
                      project: projectName,
                      objectId: model.val.name,
                      weaveKind: 'object',
                      scheme: 'weave',
                      versionHash: '',
                      path: '',
                    })
                  )
                );

                refetch();
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
            });
            setIsDrawerOpen(true);
          },
        };
      }) || [],
    [
      customProvidersResult,
      customProviderModelsResult,
      customModelsResult,
      entityName,
      projectName,
      objectDeleteAllVersions,
    ]
  );

  const refetch = () => {
    refetchCustomProviders();
    refetchCustomProviderModels();
    refetchCustomModels();
  };

  return (
    <Tailwind>
      <div className="mx-32 my-16 min-h-screen">
        <div className="flex flex-col gap-32 bg-white">
          <div>
            <div className="mb-6">
              <h2 className="mb-2 text-xl font-bold">AI providers</h2>
              <p className="text-moon-500">
                AI providers are configured at the team level.
                {isAdmin
                  ? ' Add team secrets to enable access.'
                  : ' Contact a team admin to set them up.'}
              </p>
            </div>

            <div className="flex h-full min-h-[200px] items-center justify-center">
              <ProviderTable
                columns={columns}
                providers={providers}
                loading={configuredProvidersLoading}
              />
            </div>
          </div>

          <div>
            <div>
              <div className="mb-6 flex items-center justify-between">
                <div>
                  <h2 className="mb-2 text-xl font-bold">Custom providers</h2>
                  <p className="text-moon-500">
                    Custom providers and models are configured at the project
                    level.
                  </p>
                </div>
                <Button
                  variant="secondary"
                  icon="add-new"
                  onClick={() => setIsDrawerOpen(true)}>
                  Add a provider
                </Button>
              </div>
              <ProviderTable
                columns={customColumns}
                providers={customProviders}
                loading={
                  customProvidersLoading ||
                  customProviderModelsLoading ||
                  customModelsLoading
                }
              />
            </div>
          </div>
        </div>
      </div>
      <AddProviderDrawer
        isOpen={isDrawerOpen}
        projectId={`${entityName}/${projectName}`}
        onClose={() => setIsDrawerOpen(false)}
        refetch={refetch}
        providers={customProviders.map(provider => provider.name)}
        editingProvider={editingProvider}
      />
      <DeleteModal
        open={deletingProvider != null}
        onClose={() => setDeletingProvider(null)}
        deleteTitleStr={`custom provider "${deletingProvider?.name}"?`}
        deleteBodyStrs={[
          'This action cannot be undone.',
          'All custom models and provider models will also be deleted.',
        ]}
        onDelete={deletingProvider?.deleteAction}
      />
    </Tailwind>
  );
};

export const ProvidersTab: React.FC<{
  entityName?: string;
  projectName?: string;
}> = ({entityName = '', projectName = ''}) => {
  return (
    <ApolloProvider client={makeGorillaApolloClient()}>
      <WFDataModelAutoProvider
        entityName={entityName}
        projectName={projectName}>
        <ProvidersTabInner entityName={entityName} projectName={projectName} />
      </WFDataModelAutoProvider>
    </ApolloProvider>
  );
};
