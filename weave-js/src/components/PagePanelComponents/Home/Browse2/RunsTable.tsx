import * as _ from 'lodash';
import React, {FC, useEffect, useMemo, useRef} from 'react';
import {useParams, useHistory} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import {monthRoundedTime} from '@wandb/weave/time';
import {Call, Span} from './callTree';
import {Box} from '@mui/material';
import {
  DataGridPro as DataGrid,
  GridColDef,
  GridColumnGroup,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {SmallRef} from './SmallRef';
import {parseRef} from '@wandb/weave/react';
import {flattenObject} from './browse2Util';

type DataGridColumnGroupingModel = Exclude<
  React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
  undefined
>;

function addToTree(
  node: GridColumnGroup,
  fields: string[],
  fullPath: string
): void {
  if (!fields.length) return;

  if (fields.length === 1) {
    node.children.push({
      field: fullPath,
    });
    return;
  }

  for (const child of node.children) {
    if ('groupId' in child && child.groupId === fields[0]) {
      addToTree(child as GridColumnGroup, fields.slice(1), fullPath);
      return;
    }
  }

  const newNode: GridColumnGroup = {groupId: fields[0], children: []};
  node.children.push(newNode);
  addToTree(newNode, fields.slice(1), fullPath);
}

function buildTree(strings: string[], rootGroupName: string): GridColumnGroup {
  const root: GridColumnGroup = {groupId: rootGroupName, children: []};

  for (const str of strings) {
    const fields = str.split('.');
    addToTree(root, fields, rootGroupName + '.' + str);
  }

  return root;
}

export const RunsTable: FC<{
  loading: boolean;
  spans: Span[];
}> = ({loading, spans}) => {
  const apiRef = useGridApiRef();
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
            _.omitBy(flattenObject(call.output), v => v == null),
            (v, k) => {
              return 'output.' + k;
            }
          ),
          v =>
            typeof v === 'string' ||
            typeof v === 'boolean' ||
            typeof v === 'number'
              ? v
              : JSON.stringify(v)
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
    const colGroupingModel: DataGridColumnGroupingModel = [];
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
        renderCell: params => {
          if (
            typeof params.row['input_' + key] === 'string' &&
            params.row['input_' + key].startsWith('wandb-artifact:///')
          ) {
            return <SmallRef objRef={parseRef(params.row['input_' + key])} />;
          }
          return params.row['input_' + key];
        },
      });
      inputGroup.children.push({field: 'input_' + key});
    }
    colGroupingModel.push(inputGroup);

    // All output keys as we don't have the order key yet.
    let outputKeys: {[key: string]: true} = {};
    spans.forEach(span => {
      for (const [k, v] of Object.entries(flattenObject(span.output))) {
        if (v != null) {
          outputKeys[k] = true;
        }
      }
    });
    // sort shallowest keys first
    outputKeys = _.fromPairs(
      Object.entries(outputKeys).sort((a, b) => {
        const aDepth = a[0].split('.').length;
        const bDepth = b[0].split('.').length;
        return aDepth - bDepth;
      })
    );

    const outputOrder = Object.keys(outputKeys);
    const outputGrouping = buildTree(outputOrder, 'output');
    colGroupingModel.push(outputGrouping);
    for (const key of outputOrder) {
      cols.push({
        field: 'output.' + key,
        headerName: key.split('.').slice(-1)[0],
        renderCell: params => {
          if (
            typeof params.row['output.' + key] === 'string' &&
            params.row['output.' + key].startsWith('wandb-artifact:///')
          ) {
            return <SmallRef objRef={parseRef(params.row['output.' + key])} />;
          }
          return params.row['output.' + key];
        },
      });
    }

    return {cols, colGroupingModel};
  }, [spans]);
  const autosized = useRef(false);
  useEffect(() => {
    if (autosized.current) {
      return;
    }
    if (loading) {
      return;
    }
    autosized.current = true;
    apiRef.current.autosizeColumns({
      includeHeaders: true,
      expand: true,
    });
  }, [apiRef, loading]);
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
        autosizeOnMount
        apiRef={apiRef}
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
