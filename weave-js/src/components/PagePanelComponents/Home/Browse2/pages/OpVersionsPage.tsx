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
import {basicField} from './common/DataTable';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFOpVersion} from './interface/wf/types';

export const OpVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const orm = useWeaveflowORMContext();

  const allOpVersions = useMemo(() => {
    return orm.projectConnection.opVersions();
  }, [orm.projectConnection]);
  return (
    <SimplePageLayout
      title="Ops"
      tabs={[
        {
          label: 'All',
          content: <OpVersionsTable opVersions={allOpVersions} />,
        },
      ]}
    />
  );
};

export const OpVersionsTable: React.FC<{
  opVersions: WFOpVersion[];
}> = props => {
  const history = useHistory();
  const routeContext = useWeaveflowRouteContext();
  // const allOpVersions = useAllOpVersions(props.entity, props.project);
  const rows: GridRowsProp = useMemo(() => {
    return props.opVersions.map((ov, i) => {
      return {
        id: ov.version(),
        obj: ov,
        op: ov.op().name(),
        version: ov.version(),
        description: ov.description(),
        versionIndex: ov.versionIndex(),
        createdAt: ov.createdAtMs(),
        isLatest: ov.aliases().includes('latest'),
        calls: ov.calls(),
        // code: () => string;
        // inputTypes: () => {[argName: string]: WFTypeVersion};
        // outputType: () => WFTypeVersion;
        // invokes: () => WFOpVersion[];
        // invokedBy: () => WFOpVersion[];
        // calls: () => WFCall[];
        // description: () => string;
      };
    });
  }, [props.opVersions]);
  const columns: GridColDef[] = [
    basicField('id', 'View', {
      width: 50,
      minWidth: 50,
      maxWidth: 50,
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
    basicField('op', 'Op'),
    basicField('version', 'Version'),
    // basicField('typeVersion', 'Type Version'),
    // basicField('inputTo', 'Input To'),
    // basicField('outputFrom', 'Output From'),
    basicField('description', 'Description'),
    basicField('versionIndex', 'Version Index'),
    basicField('createdAt', 'Created At'),
    basicField('isLatest', 'Is Latest'),
    basicField('calls', 'Calls'),
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
            routeContext.opVersionUIUrl(
              params.row.obj.entity(),
              params.row.obj.project(),
              params.row.op,
              params.row.version
            )
          );
        }
      }}
    />
  );
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
