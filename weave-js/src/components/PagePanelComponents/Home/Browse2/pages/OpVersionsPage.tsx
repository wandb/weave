import {Box} from '@material-ui/core';
import {Check, NavigateNext} from '@mui/icons-material';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import moment from 'moment';
import React, {useMemo} from 'react';

import {useAllOpVersions} from './interface/dataModel';

export const OpVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  return <>hi</>;
  // const allObjectVersions = useAllOpVersions(props.entity, props.project);
  // const rows: GridRowsProp = useMemo(() => {
  //   if (allObjectVersions.loading) {
  //     return [];
  //   } else {
  //     return allObjectVersions.result.map((ov, i) => {
  //       return {
  //         id: ov.artifact_id,
  //         collection_name: ov.collection_name,
  //         hash: ov.hash,
  //         is_latest_in_collection: ov.aliases.includes('latest'),
  //         version_index: ov.version_index,
  //         type_version: ov.type_version.type_name,
  //         // produced_by: ov.produced_by,
  //         created_at_ms: ov.created_at_ms,
  //         date_created: ov.created_at_ms,
  //         // date_created: moment
  //         //   .unix(ov.created_at_ms / 1000)
  //         //   .format('YYYY-MM-DD HH:mm:ss'),
  //         description: ov.description,
  //         // metadata: {},
  //         // tags: [],
  //         // properties: {a: 'b', c: 'd'},
  //       };
  //     });
  //   }
  // }, [allObjectVersions]);
  // const columns: GridColDef[] = [
  //   {
  //     field: 'id',
  //     headerName: 'View',
  //     width: 30,
  //     renderCell: params => {
  //       // Icon to indicate navigation to the object version
  //       return (
  //         <NavigateNext
  //           style={{
  //             cursor: 'pointer',
  //           }}
  //         />
  //       );
  //     },
  //   },
  //   {
  //     field: 'collection_name',
  //     headerName: 'Collection Name',
  //     flex: 1,
  //     minWidth: 100,
  //   },
  //   {field: 'hash', headerName: 'Hash', flex: 1, minWidth: 100},
  //   {
  //     field: 'is_latest_in_collection',
  //     headerName: 'Is Latest',
  //     flex: 1,
  //     minWidth: 100,
  //     renderCell: params => {
  //       return params.value ? <Check /> : null;
  //     },
  //   },
  //   {
  //     field: 'version_index',
  //     headerName: 'Version Index',
  //     flex: 1,
  //     minWidth: 100,
  //   },
  //   {field: 'type_version', headerName: 'Data Type', flex: 1, minWidth: 100},
  //   // {field: 'produced_by', headerName: 'Produced By', flex: 1, minWidth: 100},
  //   {
  //     field: 'date_created',
  //     headerName: 'Date Created',
  //     flex: 1,
  //     minWidth: 100,
  //     renderCell: params => {
  //       return moment.unix(params.value / 1000).format('YYYY-MM-DD HH:mm:ss');
  //     },
  //   },
  //   {
  //     field: 'description',
  //     headerName: 'Description',
  //     flex: 1,
  //     minWidth: 100,
  //     editable: true,
  //   },
  //   // Metadata might not be necessary right now
  //   // {field: 'metadata', headerName: 'Metadata', flex: 1, minWidth: 100},
  //   // I think tags might not be available
  //   // {field: 'tags', headerName: 'Tags'},
  //   // Properties are only shown when there is a type filter
  //   // TODO: work this out
  //   // {field: 'properties', headerName: 'Properties'},
  // ];
  // const columnGroupingModel: GridColumnGroupingModel = [];
  // return (
  //   <Box
  //     sx={{
  //       display: 'flex',
  //       flexDirection: 'column',
  //       flexGrow: 1,
  //     }}>
  //     <Box
  //       sx={{
  //         position: 'sticky',
  //         top: 0,
  //         zIndex: 1,
  //         p: 3,
  //         borderBottom: '1px solid #e0e0e0',
  //       }}>
  //       <h1>All Op (Version)s</h1>
  //     </Box>
  //     <Box
  //       component="main"
  //       sx={{
  //         flexGrow: 1,
  //         overflow: 'hidden',
  //         display: 'flex',
  //         flexDirection: 'column',
  //       }}>
  //       <DataGridPro
  //         rows={rows}
  //         initialState={{
  //           sorting: {
  //             sortModel: [{field: 'date_created', sort: 'desc'}],
  //           },
  //         }}
  //         // {...data}
  //         // loading={data.rows.length === 0}
  //         rowHeight={38}
  //         columns={columns}
  //         experimentalFeatures={{columnGrouping: true}}
  //         disableRowSelectionOnClick
  //         columnGroupingModel={columnGroupingModel}
  //         onRowClick={params => {
  //           // history.push(
  //           //   `/${props.entity}/${props.project}/objects/${params.row.collection_name}/versions/${params.row.hash}`
  //           // );
  //         }}
  //         onCellClick={params => {
  //           // TODO: move these actions into a config
  //           if (params.field === 'id') {
  //             history.push(
  //               `/${props.entity}/${props.project}/objects/${params.row.collection_name}/versions/${params.row.hash}`
  //             );
  //           }
  //         }}
  //         onCellEditStop={(params, event) => {
  //           const newVal = (event as any).target.value;
  //           if (params.field === 'description') {
  //             if (newVal === params.row.description) {
  //               return;
  //             }
  //             updateDescription(params.row.id, (event as any).target.value);
  //           }
  //         }}
  //       />
  //     </Box>
  //   </Box>
  // );
};

/* <div>
      <h1>OpVersionsPage Placeholder</h1>
      <h2>Filter: {filter}</h2>
      <div>
        This is the listing page for OpVersions. An OpVersion is a "version" of
        a weave "op". In the user's mind it is analogous to a specific
        implementation of a method.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          There are a few tables in Weaveflow that are close to this, but none
          that are exactly what we want.
        </li>
        <li>
          Notice that the sidebar `Operations` links here. This might seem like
          a mistake, but it is not. What the user most likely _wants_ to see is
          a listing of all the _latest_ versions of each op (which is why the
          link filters to latest).
        </li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Each row should link to the associated op version:{' '}
          <Link to={prefix('/ops/op_name/versions/version_id')}>
            /ops/[op_name]/versions/[version_id]
          </Link>
        </li>
      </ul>
      <div>Inspiration</div>
      This page will basically be a simple table of Op Versions, with some
      lightweight filtering on top.
      <br />
      <img
        src="https://github.com/wandb/weave/blob/db555a82512c2bac881ee0c65cf6d33264f4d34c/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/simple_table.png?raw=true"
        style={{
          width: '100%',
        }}
        alt=""
      />
    </div> */
