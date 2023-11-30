import Box from '@mui/material/Box';
// import {useDemoData} from '@mui/x-data-grid-generator';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import React from 'react';
import {Link} from 'react-router-dom';

import {useEPPrefix, useQuery} from './util';
import {Check} from '@mui/icons-material';

export const ObjectVersionsPage: React.FC = () => {
  // const search = useQuery();
  // const filter = search.filter;
  // const prefix = useEPPrefix();
  // const {data} = useDemoData({
  //   dataSet: 'Commodity',
  //   rowLength: 100000,
  //   editable: false,
  // });
  const rows: GridRowsProp = [
    {
      id: 0,
      collection_name: 'Model',
      version_id: '1234',
      is_latest_in_collection: true,
      version_index: 4,
      type_version: 'GPT:1234 -> Model:5432',
      produced_by: 'Call xyz',
      date_created: '2021-10-01',
      description: 'This is a model',
      // metadata: {},
      // tags: [],
      // properties: {a: 'b', c: 'd'},
    },
  ];
  const columns: GridColDef[] = [
    {
      field: 'collection_name',
      headerName: 'Collection Name',
      flex: 1,
      minWidth: 100,
    },
    {field: 'version_id', headerName: 'Version ID', flex: 1, minWidth: 100},
    {
      field: 'is_latest_in_collection',
      headerName: 'Is Latest',
      flex: 1,
      minWidth: 100,
      renderCell: params => {
        return params.value ? <Check /> : <Check />;
      },
    },
    {
      field: 'version_index',
      headerName: 'Version Index',
      flex: 1,
      minWidth: 100,
    },
    {field: 'type_version', headerName: 'Data Type', flex: 1, minWidth: 100},
    {field: 'produced_by', headerName: 'Produced By', flex: 1, minWidth: 100},
    {field: 'date_created', headerName: 'Date Created', flex: 1, minWidth: 100},
    {field: 'description', headerName: 'Description', flex: 1, minWidth: 100},
    // Metadata might not be necessary right now
    // {field: 'metadata', headerName: 'Metadata', flex: 1, minWidth: 100},
    // I think tags might not be available
    // {field: 'tags', headerName: 'Tags'},
    // Properties are only shown when there is a type filter
    // TODO: work this out
    // {field: 'properties', headerName: 'Properties'},
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];
  return (
    <Box
      sx={{
        flex: '1 1 auto',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        display: 'flex',
      }}>
      <Box sx={{flex: '1 1 auto', overflow: 'hidden'}}>
        <DataGridPro
          rows={rows}
          // {...data}
          // loading={data.rows.length === 0}
          rowHeight={38}
          columns={columns}
          experimentalFeatures={{columnGrouping: true}}
          disableRowSelectionOnClick
          columnGroupingModel={columnGroupingModel}
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
        <Link to={prefix('/objects/object_name/versions/version_id')}>
          /objects/object_name/versions/version_id
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
