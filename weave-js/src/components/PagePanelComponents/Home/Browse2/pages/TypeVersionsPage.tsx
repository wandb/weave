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
import {useWeaveflowORMContext} from './interface/wf/context';

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

export const TypeVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const history = useHistory();
  const routeContext = useWeaveflowRouteContext();
  const orm = useWeaveflowORMContext();

  const allTypeVersions = useMemo(() => {
    return orm.projectConnection.typeVersions();
  }, [orm.projectConnection]);
  // const allObjectVersions = useAllObjectVersions(props.entity, props.project);
  const rows: GridRowsProp = useMemo(() => {
    return allTypeVersions.map((tv, i) => {
      return {
        id: tv.version(),
        type: tv.type().name(),
        version: tv.version(),
        parentType: tv.parentTypeVersion(),
        childTypes: tv.childTypeVersions(),
        // inputTo: tv.inputTo(),
        // outputFrom: tv.outputFrom(),
        objectVersions: tv.objectVersions(),
      };
    });
  }, [allTypeVersions]);
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
    basicField('type', 'Type'),
    basicField('version', 'Version'),
    basicField('parentType', 'Parent Type'),
    basicField('childTypes', 'Child Types'),
    basicField('inputTo', 'Input To'),
    basicField('outputFrom', 'Output From'),
    basicField('objectVersions', 'Object Versions'),
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          p: 3,
          borderBottom: '1px solid #e0e0e0',
        }}>
        <h1>All Type (Version)s</h1>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
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
                routeContext.typeVersionUIUrl(
                  props.entity,
                  props.project,
                  params.row.type,
                  params.row.version
                )
              );
            }
          }}
        />
      </Box>
    </Box>
  );
};

// <div>
//       <h1>TypeVersionsPage Placeholder</h1>
//       <h2>Filter: {filter}</h2>
//       <div>
//         This is the listing page for TypeVersions. A TypeVersion is a "version"
//         of a weave "type". In the user's mind it is analogous to a specific
//         implementation of a python class.
//       </div>
//       <div>Migration Notes:</div>
//       <ul>
//         <li>
//           From a content perspective, this is similar to the `versions` table
//           available in weaveflow (
//           <a href="https://weave.wandb.ai/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset">
//             example
//           </a>
//           ) except that rather than just showing the versions of a single type,
//           we show all versions of all types, filtered to whatever the user (or
//           link source) specified.
//         </li>
//         <li>
//           Notice that the sidebar `Types` links here. This might seem like a
//           mistake, but it is not. What the user most likely _wants_ to see is a
//           listing of all the _latest_ versions of each type (which is why the
//           link filters to latest).
//         </li>
//       </ul>
//       <div>Links:</div>
//       <ul>
//         <li>
//           Each row should link to the associated type version:{' '}
//           <Link to={prefix('/types/type_name/versions/version_id')}>
//             /types/[type_name]/versions/[version_id]
//           </Link>
//         </li>
//       </ul>
//       <div>Inspiration</div>
//       This page will basically be a simple table of Type Versions, with some
//       lightweight filtering on top.
//       <br />
//       <img
//         src="https://github.com/wandb/weave/blob/db555a82512c2bac881ee0c65cf6d33264f4d34c/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/simple_table.png?raw=true"
//         style={{
//           width: '100%',
//         }}
//         alt=""
//       />
//     </div>
