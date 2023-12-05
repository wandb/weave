import {Box} from '@material-ui/core';
import {NavigateNext} from '@mui/icons-material';
import {Chip} from '@mui/material';
import {
  DataGridPro,
  GridColDef,
  GridColumnGroupingModel,
  GridRowsProp,
} from '@mui/x-data-grid-pro';
import moment from 'moment';
import React, {useMemo} from 'react';
import {Link, useHistory} from 'react-router-dom';

import {useWeaveflowRouteContext} from '../context';
import {basicField} from './common/DataTable';
import {ObjectLink, OpVersionLink, TypeVersionLink} from './common/Links';
import {SimplePageLayout} from './common/SimplePageLayout';
import {useWeaveflowORMContext} from './interface/wf/context';
import {WFObjectVersion} from './interface/wf/types';

export const ObjectVersionsPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  const orm = useWeaveflowORMContext();
  const allObjectVersions = useMemo(() => {
    return orm.projectConnection.objectVersions();
  }, [orm.projectConnection]);

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
      const outputFrom = ov.outputFrom();
      const firstOutputFromOpVersion =
        outputFrom.length > 0 ? outputFrom[0].opVersion() : null;
      const firstOutputFrom = firstOutputFromOpVersion
        ? firstOutputFromOpVersion.op().name() +
          ':' +
          firstOutputFromOpVersion.version()
        : null;
      return {
        id: ov.version(),
        obj: ov,
        object: ov.object().name(),
        version: ov.version(),
        typeVersion:
          ov.typeVersion().type().name() + ':' + ov.typeVersion().version(),
        inputTo: ov.inputTo().length,
        outputFrom: firstOutputFrom,
        description: ov.description(),
        versionIndex: ov.versionIndex(),
        createdAt: ov.createdAtMs(),
        isLatest: ov.aliases().includes('latest'),
      };
    });
  }, [props.objectVersions]);
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
    basicField('object', 'Object', {
      renderCell: params => <ObjectLink objectName={params.value as string} />,
    }),
    basicField('version', 'Version', {}),
    basicField('typeVersion', 'Type Version', {
      renderCell: params => (
        <TypeVersionLink
          typeName={params.row.obj.typeVersion().type().name()}
          version={params.row.obj.typeVersion().version()}
        />
      ),
    }),
    basicField('inputTo', 'Input To', {
      renderCell: params => {
        if (params.value === 0) {
          return '';
        }

        return (
          <Link to={''}>{params.value} calls (TODO: link with filter)</Link>
        );
      },
    }),
    basicField('outputFrom', 'Output From', {
      renderCell: params => {
        if (!params.value) {
          return '';
        }
        const outputFrom = params.row.obj.outputFrom();
        if (outputFrom.length === 0) {
          return '';
        }
        if (outputFrom.length === 1) {
          return (
            <OpVersionLink
              opName={outputFrom[0].opVersion().op().name()}
              version={outputFrom[0].opVersion().version()}
            />
          );
        }
        return (
          <Link to={''}>
            {outputFrom.length} calls (TODO: link with filter)
          </Link>
        );
      },
    }),
    basicField('description', 'Description'),
    basicField('versionIndex', 'Version'),
    basicField('createdAt', 'Created At', {
      renderCell: params => {
        return moment(params.value as number).format('YYYY-MM-DD HH:mm:ss');
      },
    }),
    basicField('isLatest', 'Latest', {
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
