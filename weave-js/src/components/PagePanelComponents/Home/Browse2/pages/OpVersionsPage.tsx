import {Box, Chip} from '@material-ui/core';
import {NavigateNext} from '@mui/icons-material';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import moment from 'moment';
import React, {useMemo} from 'react';
import {useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../context';
import {basicField} from './common/DataTable';
import {CallsLink, OpLink, OpVersionLink} from './common/Links';
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
      title="Op Versions"
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
        calls: ov.calls().length,
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
    basicField('createdAt', 'Created At', {
      width: 150,
      renderCell: params => {
        return moment(params.value as number).format('YYYY-MM-DD HH:mm:ss');
      },
    }),
    basicField('version', 'Version', {
      width: 175,
      renderCell: params => {
        return (
          <OpVersionLink
            opName={params.row.op}
            version={params.value}
            hideName
          />
        );
      },
    }),

    basicField('op', 'Op', {
      renderCell: params => <OpLink opName={params.value as string} />,
    }),
    basicField('calls', 'Calls', {
      width: 100,
      renderCell: params => {
        if (params.value === 0) {
          return '';
        }

        return (
          <CallsLink
            entity={params.row.obj.entity()}
            project={params.row.obj.project()}
            callCount={params.value}
            filter={{
              opVersions: [
                params.row.obj.op().name() + ':' + params.row.obj.version(),
              ],
            }}
          />
        );
      },
    }),
    // basicField('typeVersion', 'Type Version'),
    // basicField('inputTo', 'Input To'),
    // basicField('outputFrom', 'Output From'),
    basicField('description', 'Description'),
    basicField('versionIndex', 'Version Index', {
      width: 100,
    }),

    basicField('isLatest', 'Latest', {
      width: 100,
      renderCell: params => {
        if (params.value) {
          return (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                width: '100%',
              }}>
              <Chip label="Yes" size="small" />
            </Box>
          );
        }
        return '';
      },
    }),
  ];
  const columnGroupingModel: GridColumnGroupingModel = [];
  return (
    <DataGridPro
      rows={rows}
      initialState={{
        sorting: {
          sortModel: [{field: 'createdAt', sort: 'desc'}],
        },
      }}
      rowHeight={38}
      columns={columns}
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
      columnGroupingModel={columnGroupingModel}
      onCellClick={params => {
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
