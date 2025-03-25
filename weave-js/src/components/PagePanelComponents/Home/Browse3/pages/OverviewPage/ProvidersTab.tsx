import {ApolloProvider} from '@apollo/client';
import {GridColDef, GridRenderCellParams} from '@mui/x-data-grid-pro';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Button} from '@wandb/weave/components/Button';
import {Icon} from '@wandb/weave/components/Icon';
import {Pill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {Timestamp} from '@wandb/weave/components/Timestamp';
import React, {useState} from 'react';

import {DeleteModal} from '../common/DeleteModal';
import {Link} from '../common/Links';
import {useConfiguredProviders} from '../PlaygroundPage/useConfiguredProviders';
import {WFDataModelAutoProvider} from '../wfReactInterface/context';
import {AddProviderDrawer} from './AddProviderDrawer';
import {ProviderTable} from './ProviderTable';
import {useCustomProviders} from './useCustomProviders';

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
    headerName: 'Name',
    flex: 0.2,
    minWidth: 200,
  },
  {
    field: 'status',
    headerName: 'Status',
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
        <span
          className="text-moon-500"
          style={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            maxWidth: '100%',
            display: 'inline-block',
          }}>
          {params.value || 'None'}
        </span>
        {params.row.isAdmin && !params.row.status && (
          <Link
            to={`/${params.row.entityName}/settings`}
            $variant="secondary"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2">
            Add team secret
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
    headerName: 'Name',
    flex: 0.25,
    minWidth: 200,
  },
  {
    field: 'models',
    headerName: 'Models',
    flex: 0.25,
    minWidth: 200,
  },
  {
    field: 'lastUpdated',
    headerName: 'Last updated',
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
  entityName: string;
  projectName: string;
}> = ({entityName, projectName}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<any>(null);
  const [deletingProvider, setDeletingProvider] = useState<any>(null);
  const {loading: loadingUserInfo, userInfo} = useViewerInfo();
  const isAdmin = !loadingUserInfo && userInfo?.roles[entityName] === 'admin';

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

  // Use our custom hook for custom providers
  const {customProviders, customProvidersLoading, refetch} = useCustomProviders(
    {
      entityName,
      projectName,
      setEditingProvider,
      setIsDrawerOpen,
      setDeletingProvider,
    }
  );

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
                loading={customProvidersLoading}
              />
            </div>
          </div>
        </div>
      </div>
      <AddProviderDrawer
        entityName={entityName}
        projectName={projectName}
        isOpen={isDrawerOpen}
        projectId={`${entityName}/${projectName}`}
        onClose={() => setIsDrawerOpen(false)}
        refetch={refetch}
        providers={
          customProviders
            .map(provider => provider.name)
            .filter(Boolean) as string[]
        }
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
  entityName: string;
  projectName: string;
}> = ({entityName, projectName}) => {
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
