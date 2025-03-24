import {ApolloProvider} from '@apollo/client';
import {GridColDef, GridRenderCellParams} from '@mui/x-data-grid-pro';
import {makeGorillaApolloClient} from '@wandb/weave/apollo';
import {useViewerInfo} from '@wandb/weave/common/hooks/useViewerInfo';
import {Icon} from '@wandb/weave/components/Icon';
import {Pill} from '@wandb/weave/components/Tag';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React from 'react';

import {Link} from '../common/Links';
import {useConfiguredProviders} from '../PlaygroundPage/useConfiguredProviders';
import {WFDataModelAutoProvider} from '../wfReactInterface/context';
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
        <span className="text-moon-500">{params.value || 'None'}</span>
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

export const ProvidersTabInner: React.FC<{
  entityName: string;
}> = ({entityName}) => {
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
        </div>
      </div>
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
        <ProvidersTabInner entityName={entityName} />
      </WFDataModelAutoProvider>
    </ApolloProvider>
  );
};
