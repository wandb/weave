import {GridColDef, GridRowParams, GridRowsProp} from '@mui/x-data-grid-pro';
import _ from 'lodash';
import React from 'react';
import {useHistory} from 'react-router-dom';

import {monthRoundedTime} from '../../../../../../common/util/time';
import {Button} from '../../../../../Button';
import {Pill} from '../../../../../Tag';
import {Tooltip} from '../../../../../Tooltip';
import {useWeaveflowRouteContext} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {opNiceName} from '../common/Links';
import {WANDB_ARTIFACT_REF_PREFIX} from '../wfReactInterface/constants';
import {
  CallSchema,
  refUriToOpVersionKey,
  useOpVersions,
} from '../wfReactInterface/interface';

type ChildCallSummaryTableProps = {
  parent: CallSchema;
  calls: CallSchema[];
  onSelectionChange: (selection: string[]) => void;
};

export const ChildCallSummaryTable = ({
  parent,
  calls,
  onSelectionChange,
}: ChildCallSummaryTableProps) => {
  const history = useHistory();
  const {baseRouter} = useWeaveflowRouteContext();

  const sorted = _.sortBy(calls, c => c.rawSpan.timestamp);
  const grouped = _.groupBy(sorted, c => c.opVersionRef ?? c.spanName);

  const entityName = calls[0].entity;
  const projectName = calls[0].project;
  const opIds = Object.keys(grouped)
    .map(key =>
      key.startsWith(WANDB_ARTIFACT_REF_PREFIX)
        ? refUriToOpVersionKey(key).opId
        : ''
    )
    .filter(v => v.length);
  const opVersions = useOpVersions(entityName, projectName, {
    opIds,
  });
  const opVersionsMap = _.keyBy(opVersions.result ?? [], 'opId');

  const columns: GridColDef[] = [
    {
      field: 'id',
      headerName: 'Operation',
      minWidth: 100,
      width: 200,
      flex: 1,
      renderCell: cellParams => {
        const opv = cellParams.row.opVersion;
        if (!opv) {
          return cellParams.row.id;
        }
        return `${opNiceName(opv.opId)}:v${opv.versionIndex}`;
      },
    },
    {
      field: 'numCalls',
      headerName: '# of Calls',
      align: 'right',
      headerAlign: 'right',
      renderCell: cellParams => cellParams.row.numCalls.toLocaleString(),
    },
    {
      field: 'pctSuccess',
      headerName: 'Status',
      renderCell: cellParams => {
        const {pctSuccess, numSuccess, numError} = cellParams.row;
        // Not using StatusChip because we have a custom tooltip and label.
        const trigger = (
          <div style={{display: 'flex', gap: '4px'}}>
            {numSuccess > 0 && (
              <Pill
                icon="checkmark-circle"
                color="green"
                label={numSuccess.toLocaleString()}
              />
            )}
            {numError > 0 && (
              <Pill
                icon="failed"
                color="red"
                label={numError.toLocaleString()}
              />
            )}
          </div>
        );
        return (
          <Tooltip content={`${pctSuccess}% Succeeded`} trigger={trigger} />
        );
      },
    },
    {
      field: 'numSuccess',
      headerName: '# Succeeded',
      align: 'right',
      headerAlign: 'right',
      renderCell: cellParams => cellParams.row.numSuccess.toLocaleString(),
    },
    {
      field: 'numError',
      headerName: '# Errored',
      align: 'right',
      headerAlign: 'right',
      renderCell: cellParams => cellParams.row.numError.toLocaleString(),
    },
    {
      field: 'meanLatency',
      headerName: 'Mean Latency',
      renderCell: cellParams => {
        return monthRoundedTime(cellParams.row.meanLatency);
      },
    },
    {
      field: 'actions',
      headerName: '',
      width: 130,
      resizable: false,
      sortable: false,
      renderCell: cellParams => {
        const {id} = cellParams.row;
        if (!id.startsWith(WANDB_ARTIFACT_REF_PREFIX)) {
          return null;
        }
        return (
          <Button
            variant="secondary"
            size="small"
            icon="share-export"
            onClick={() => {
              history.push(
                baseRouter.callsUIUrl(entityName, projectName, {
                  opVersionRefs: [id],
                  parentId: parent.callId,
                })
              );
            }}>
            Go to table
          </Button>
        );
      },
    },
  ];

  const rows: GridRowsProp = Object.entries(grouped).map(([op, opcalls]) => {
    const opVersion = opVersionsMap[opcalls[0].spanName];
    const numCalls = opcalls.length;
    // Note: We're likely to have run ops in parallel, so displaying latency sum might be confusing.
    const latencies = opcalls.map(c => c.rawSpan.summary.latency_s);
    const meanLatency = _.sum(latencies) / numCalls;
    const statuses = _.countBy(opcalls, c => c.rawSpan.status_code);
    const numSuccess = statuses.SUCCESS ?? 0;
    const numError = statuses.ERROR ?? 0;
    const pctSuccess = (numSuccess / numCalls) * 100;
    return {
      id: op,
      opVersion,
      numCalls,
      meanLatency,
      numSuccess,
      numError,
      pctSuccess,
    };
  });

  return (
    <StyledDataGrid
      columns={columns}
      rows={rows}
      rowHeight={38}
      autoHeight={true}
      hideFooter
      checkboxSelection
      initialState={{
        columns: {
          columnVisibilityModel: {
            numSuccess: false,
            numError: false,
          },
        },
      }}
      isRowSelectable={(params: GridRowParams) =>
        params.row.id.startsWith(WANDB_ARTIFACT_REF_PREFIX)
      }
      onRowSelectionModelChange={rowSelectionModel => {
        onSelectionChange(rowSelectionModel.map(r => r.toString()));
      }}
    />
  );
};
