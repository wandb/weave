import {Check, NavigateNext} from '@mui/icons-material';
import Box from '@mui/material/Box';
// import {useDemoData} from '@mui/x-data-grid-generator';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import moment from 'moment';
import React, {useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {
  useAllObjectVersions,
  useUpdateObjectVersionDescription,
} from './interface/dataModel';

export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const history = useHistory();
  const allObjectVersions = useAllObjectVersions(props.entity, props.project);
  const rows: GridRowsProp = useMemo(() => {
    if (allObjectVersions.loading) {
      return [];
    } else {
      return allObjectVersions.result.map((ov, i) => {
        return {
          id: ov.artifact_id,
          collection_name: ov.collection_name,
          hash: ov.hash,
          is_latest_in_collection: ov.aliases.includes('latest'),
          version_index: ov.version_index,
          type_version: ov.type_version.type_name,
          // produced_by: ov.produced_by,
          created_at_ms: ov.created_at_ms,
          date_created: ov.created_at_ms,
          // date_created: moment
          //   .unix(ov.created_at_ms / 1000)
          //   .format('YYYY-MM-DD HH:mm:ss'),
          description: ov.description,
          // metadata: {},
          // tags: [],
          // properties: {a: 'b', c: 'd'},
        };
      });
    }
  }, [allObjectVersions]);
  // const rows: GridRowsProp = [
  //   {
  //     // id: 0,
  //     collection_name: 'Model',
  //     hash: '1234',
  //     is_latest_in_collection: true,
  //     version_index: 4,
  //     type_version: 'GPT:1234 -> Model:5432',
  //     // TODO: Tim: We need an efficient way to look up the producing call.
  //     produced_by: 'Call xyz',
  //     date_created: '2021-10-01',
  //     description: 'This is a model',
  //     // metadata: {},
  //     // tags: [],
  //     // properties: {a: 'b', c: 'd'},
  //   },
  // ];
  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'View',
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
    },
    {
      field: 'collection_name',
      headerName: 'Collection Name',
      flex: 1,
      minWidth: 100,
    },
    {field: 'hash', headerName: 'Hash', flex: 1, minWidth: 100},
    {
      field: 'is_latest_in_collection',
      headerName: 'Is Latest',
      flex: 1,
      minWidth: 100,
      renderCell: params => {
        return params.value ? <Check /> : null;
      },
    },
    {
      field: 'version_index',
      headerName: 'Version Index',
      flex: 1,
      minWidth: 100,
    },
    {field: 'type_version', headerName: 'Data Type', flex: 1, minWidth: 100},
    // {field: 'produced_by', headerName: 'Produced By', flex: 1, minWidth: 100},
    {
      field: 'date_created',
      headerName: 'Date Created',
      flex: 1,
      minWidth: 100,
      renderCell: params => {
        return moment.unix(params.value / 1000).format('YYYY-MM-DD HH:mm:ss');
      },
    },
    {
      field: 'description',
      headerName: 'Description',
      flex: 1,
      minWidth: 100,
      editable: true,
    },
    // Metadata might not be necessary right now
    // {field: 'metadata', headerName: 'Metadata', flex: 1, minWidth: 100},
    // I think tags might not be available
    // {field: 'tags', headerName: 'Tags'},
    // Properties are only shown when there is a type filter
    // TODO: work this out
    // {field: 'properties', headerName: 'Properties'},
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];
  const updateDescription = useUpdateObjectVersionDescription();
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <h1>All Object (Version)s</h1>
      <Box sx={{flex: '1 1 auto', overflow: 'hidden'}}>
        <DataGridPro
          rows={rows}
          initialState={{
            sorting: {
              sortModel: [{field: 'date_created', sort: 'desc'}],
            },
          }}
          // {...data}
          // loading={data.rows.length === 0}
          rowHeight={38}
          columns={columns}
          experimentalFeatures={{columnGrouping: true}}
          disableRowSelectionOnClick
          columnGroupingModel={columnGroupingModel}
          onRowClick={params => {
            // history.push(
            //   `/${props.entity}/${props.project}/objects/${params.row.collection_name}/versions/${params.row.hash}`
            // );
          }}
          onCellClick={params => {
            // TODO: move these actions into a config
            if (params.field === 'id') {
              history.push(
                `/${props.entity}/${props.project}/objects/${params.row.collection_name}/versions/${params.row.hash}`
              );
            }
          }}
          onCellEditStop={(params, event) => {
            const newVal = (event as any).target.value;
            if (params.field === 'description') {
              if (newVal === params.row.description) {
                return;
              }
              updateDescription(params.row.id, (event as any).target.value);
            }
          }}
        />
      </Box>
    </Box>
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
