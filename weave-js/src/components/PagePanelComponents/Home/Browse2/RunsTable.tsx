import * as _ from 'lodash';
import React, {FC, useMemo} from 'react';
import {useParams, useHistory} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import {monthRoundedTime} from '@wandb/weave/time';
import {Call, Span} from './callTree';
import {Box} from '@mui/material';
import {DataGridPro as DataGrid, GridColDef} from '@mui/x-data-grid-pro';
import {Browse2RootObjectVersionItemParams} from './CommonLib';

type DataGridColumnGroupingModel = Exclude<
  React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
  undefined
>;

export const RunsTable: FC<{
  spans: Span[];
}> = ({spans}) => {
  // Have to add _result when null, even though we try to do this in the python
  // side
  spans = useMemo(
    () =>
      spans.map(s => ({
        ...s,
        output: s.output == null ? {_result: null} : s.output,
      })),
    [spans]
  );
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const history = useHistory();
  const tableData = useMemo(() => {
    return spans.map((call: Call) => {
      const argOrder = call.inputs._input_order;
      let args = _.fromPairs(
        Object.entries(call.inputs).filter(
          ([k, c]) => c != null && !k.startsWith('_')
        )
      );
      if (argOrder) {
        args = _.fromPairs(argOrder.map((k: string) => [k, args[k]]));
      }

      return {
        id: call.span_id,
        trace_id: call.trace_id,
        status_code: call.status_code,
        timestamp: call.timestamp,
        latency: monthRoundedTime(call.summary.latency_s, true),
        ..._.mapKeys(
          _.omitBy(args, v => v == null),
          (v, k) => {
            return 'input_' + k;
          }
        ),
        ..._.mapValues(
          _.mapKeys(
            _.omitBy(call.output, v => v == null),
            (v, k) => {
              return 'output_' + k;
            }
          ),
          JSON.stringify
        ),
      };
    });
  }, [spans]);
  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        field: 'timestamp',
        headerName: 'Timestamp',
      },
      {
        field: 'latency',
        headerName: 'Latency',
      },
      {
        field: 'status_code',
        headerName: 'Status',
      },
    ];
    const colGroupingModel: DataGridColumnGroupingModel = [
      {
        headerName: '',
        groupId: 'timestamp',
        children: [{field: 'timestamp'}],
      },
      {
        headerName: '',
        groupId: 'latency',
        children: [{field: 'latency'}],
      },
    ];
    const row0 = spans[0];
    if (row0 == null) {
      return {cols: [], colGroupingModel: []};
    }

    const inputOrder =
      row0.inputs._arg_order ??
      Object.keys(_.omitBy(row0.inputs, v => v == null)).filter(
        k => !k.startsWith('_')
      );
    const inputGroup: Exclude<
      React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
      undefined
    >[number] = {
      groupId: 'inputs',
      children: [],
    };
    for (const key of inputOrder) {
      cols.push({
        field: 'input_' + key,
        headerName: key,
        flex: 1,
      });
      inputGroup.children.push({field: 'input_' + key});
    }
    colGroupingModel.push(inputGroup);

    // All output keys as we don't have the order key yet.
    let outputKeys: {[key: string]: true} = {};
    spans.forEach(span => {
      for (const [k, v] of Object.entries(span.output)) {
        if (v != null) {
          outputKeys[k] = true;
        }
      }
    });

    const outputOrder = Object.keys(outputKeys);
    const outputGroup: Exclude<
      React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
      undefined
    >[number] = {
      groupId: 'output',
      children: [],
    };
    for (const key of outputOrder) {
      cols.push({
        field: 'output_' + key,
        headerName: key,
        flex: 1,
      });
      outputGroup.children.push({field: 'output_' + key});
    }
    colGroupingModel.push(outputGroup);

    return {cols, colGroupingModel};
  }, [spans]);
  return (
    <Box
      sx={{
        height: 460,
        width: '100%',
        '& .MuiDataGrid-root': {
          border: 'none',
        },
        '& .MuiDataGrid-row': {
          cursor: 'pointer',
        },
      }}>
      <DataGrid
        density="compact"
        experimentalFeatures={{columnGrouping: true}}
        rows={tableData}
        columns={columns.cols}
        columnGroupingModel={columns.colGroupingModel}
        initialState={{
          pagination: {
            paginationModel: {
              pageSize: 10,
            },
          },
        }}
        disableRowSelectionOnClick
        onRowClick={rowParams =>
          history.push(
            `/${URL_BROWSE2}/${params.entity}/${params.project}/trace/${rowParams.row.trace_id}/${rowParams.row.id}`
          )
        }
      />
    </Box>
  );
};
