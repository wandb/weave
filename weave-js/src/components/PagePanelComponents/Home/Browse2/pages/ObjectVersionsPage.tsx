import {Box} from '@material-ui/core';
import {NavigateNext} from '@mui/icons-material';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import React, {useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../context';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFObjectVersion} from './interface/wf/types';

const basicField = (
  field: string,
  headerName: string,
  extra?: Partial<GridColDef>
): GridColDef => {
  return {
    field,
    headerName,
    flex: extra?.flex ?? 1,
    minWidth: extra?.minWidth ?? 100,
    ...extra,
  };
};
export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const orm = useWeaveflowORMContext();
  const allObjectVersions = useMemo(() => {
    return orm.projectConnection.objectVersions();
  }, [orm.projectConnection]);
  // const allObjectVersions = useAllObjectVersions(props.entity, props.project);

  return (
    <SimplePageLayout
      title="Object Versions"
      tabs={[
        {
          label: 'All',
          content: <ObjectVersionsTable objectVersions={allObjectVersions} />,
        },
      ]}
    />
  );
};

export const ObjectVersionsTable: React.FC<{
  objectVersions: WFObjectVersion[];
}> = props => {
  const history = useHistory();
  const routeContext = useWeaveflowRouteContext();
  const rows: GridRowsProp = useMemo(() => {
    return props.objectVersions.map((ov, i) => {
      return {
        id: ov.version(),
        obj: ov,
        object: ov.object().name(),
        version: ov.version(),
        typeVersion: ov.typeVersion(),
        inputTo: ov.inputTo(),
        outputFrom: ov.outputFrom(),
        description: ov.description(),
        versionIndex: ov.versionIndex(),
        createdAt: ov.createdAtMs(),
        isLatest: ov.aliases().includes('latest'),
      };
    });
  }, [props.objectVersions]);
  const columns: GridColDef[] = [
    basicField('id', 'View', {
      width: 30,
      renderCell: params => {
        // Icon to indicate navigation to the object version
        return (
          <NavigateNext
            style={{
              cursor: 'pointer',
            }}
          />
        );
      },
    }),
    basicField('object', 'Object'),
    basicField('version', 'Version'),
    basicField('typeVersion', 'Type Version'),
    basicField('inputTo', 'Input To'),
    basicField('outputFrom', 'Output From'),
    basicField('description', 'Description'),
    basicField('versionIndex', 'Version Index'),
    basicField('createdAt', 'Created At'),
    basicField('isLatest', 'Is Latest'),
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];
  return (
    <DataGridPro
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'date_created', sort: 'desc'}],
        },
      }}
      rowHeight={38}
      columns={columns}
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
      columnGroupingModel={columnGroupingModel}
      onCellClick={params => {
        // TODO: move these actions into a config
        if (params.field === 'id') {
          history.push(
            routeContext.objectVersionUIUrl(
              params.row.obj.entity(),
              params.row.obj.project(),
              params.row.object,
              params.row.version
            )
          );
        }
      }}
    />
  );
};

/* <div>
    <h1>ObjectVersionsPage Placeholder</h1>
    <h2>Filter: {filter}</h2>
    <div>
      This is <strong>A VERY IMPORTANT PAGE</strong>. This is a rich, realtime
      datagrid of all ObjectVersions. It is critical that linkers and users
      can filter this page to see exactly what they want. Moreover, it is
      critical that the user can view in a board. The user should also be able
      to do more advanced things like pivot, unnest, etc... in order to create
      comparison or analysis views inline. Plots should be automatically
      generated above the tables. The featureset is very similar to the
      CallsPage, but operating on ObjectVersions.
    </div>
    <div>Migration Notes:</div>
    <ul>
      <li>
        THIS IS COMPLETELY MISSING IN WEAVEFLOW. There is a VersionsTable, but
        it is nearly empty and not filterable/dynamic and scoped to a single
        object.
      </li>
    </ul>
    <div>Links:</div>
    <ul>
      <li>
        Each row should link to the associated ObjectVersion:{' '}
        <Link to={prefix('/objects/object_name/versions/hash')}>
          /objects/object_name/versions/hash
        </Link>
        . Note: This might prefer to be a slideout like Notion rather than a
        full link to allow for "peeking".
      </li>
      <li>
        Each row might also special link to the producing call:{' '}
        <Link to={prefix('/calls/call_id')}>/calls/call_id</Link>
      </li>
    </ul>
    <div>Inspiration</div>
    The Datadog Traces page is a great point of inspiration for this page.
    <br />
    <img
      src="https://github.com/wandb/weave/blob/7cbb458e83a7121042af6ab6894f999210fafa4d/weave-js/src/components/PagePanelComponents/Home/dd_placeholder.png?raw=true"
      style={{
        width: '100%',
      }}
      alt=""
    />
  </div> */
