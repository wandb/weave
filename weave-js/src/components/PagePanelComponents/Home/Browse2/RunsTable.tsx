import * as _ from 'lodash';
import React, {FC, useEffect, useMemo, useRef} from 'react';
import {useParams, Link} from 'react-router-dom';
import {URL_BROWSE2} from '../../../../urls';
import {monthRoundedTime} from '@wandb/weave/time';
import {SpanWithFeedback} from './callTree';
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
  spans: SpanWithFeedback[];
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
  const tableData = useMemo(() => {
    return spans.map((call: SpanWithFeedback) => {
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
        ..._.mapValues(
          _.mapKeys(
            _.omitBy(args, v => v == null),
            (v, k) => {
              return 'input_' + k;
            }
          ),
          v =>
            typeof v === 'string' ||
            typeof v === 'boolean' ||
            typeof v === 'number'
              ? v
              : JSON.stringify(v)
        ),
        ..._.mapValues(
          _.mapKeys(
            _.omitBy(
              flattenObject(call.output!),
              (v, k) => v == null || (k.startsWith('_') && k !== '_result')
            ),
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
        ..._.mapKeys(
          flattenObject(call.feedback ?? {}),
          (v, k) => 'feedback.' + k
        ),
        ..._.mapKeys(
          flattenObject(call.attributes ?? {}),
          (v, k) => 'attributes.' + k
        ),
      };
    });
  }, [spans]);
  console.log('TABLE DATA', tableData);
  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        field: 'span_id',
        headerName: 'Trace span',
        renderCell: rowParams => {
          return (
            <Link
              to={`/${URL_BROWSE2}/${params.entity}/${params.project}/trace/${rowParams.row.trace_id}/${rowParams.row.id}`}>
              {rowParams.row.id}
            </Link>
          );
        },
      },
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

    let attributesKeys: {[key: string]: true} = {};
    spans.forEach(span => {
      for (const [k, v] of Object.entries(flattenObject(span.attributes!))) {
        if (v != null && k !== '_keys') {
          attributesKeys[k] = true;
        }
      }
    });
    // sort shallowest keys first
    attributesKeys = _.fromPairs(
      Object.entries(attributesKeys).sort((a, b) => {
        const aDepth = a[0].split('.').length;
        const bDepth = b[0].split('.').length;
        return aDepth - bDepth;
      })
    );

    const attributesOrder = Object.keys(attributesKeys);
    const attributesGrouping = buildTree(attributesOrder, 'attributes');
    colGroupingModel.push(attributesGrouping);
    for (const key of attributesOrder) {
      cols.push({
        field: 'attributes.' + key,
        headerName: key.split('.').slice(-1)[0],
        renderCell: params => {
          if (
            typeof params.row['attributes.' + key] === 'string' &&
            params.row['attributes.' + key].startsWith('wandb-artifact:///')
          ) {
            return (
              <SmallRef objRef={parseRef(params.row['attributes.' + key])} />
            );
          }
          return params.row['attributes.' + key];
        },
      });
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
      for (const [k, v] of Object.entries(flattenObject(span.output!))) {
        if (v != null && (!k.startsWith('_') || k === '_result')) {
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

    let feedbackKeys: {[key: string]: true} = {};
    spans.forEach(span => {
      for (const [k, v] of Object.entries(flattenObject(span.feedback!))) {
        if (v != null && k !== '_keys') {
          feedbackKeys[k] = true;
        }
      }
    });
    // sort shallowest keys first
    feedbackKeys = _.fromPairs(
      Object.entries(feedbackKeys).sort((a, b) => {
        const aDepth = a[0].split('.').length;
        const bDepth = b[0].split('.').length;
        return aDepth - bDepth;
      })
    );

    const feedbackOrder = Object.keys(feedbackKeys);
    const feedbackGrouping = buildTree(feedbackOrder, 'feedback');
    colGroupingModel.push(feedbackGrouping);
    for (const key of feedbackOrder) {
      cols.push({
        field: 'feedback.' + key,
        headerName: key.split('.').slice(-1)[0],
        renderCell: params => {
          if (
            typeof params.row['feedback.' + key] === 'string' &&
            params.row['feedback.' + key].startsWith('wandb-artifact:///')
          ) {
            return (
              <SmallRef objRef={parseRef(params.row['feedback.' + key])} />
            );
          }
          return params.row['feedback.' + key];
        },
      });
    }

    return {cols, colGroupingModel};
  }, [params.entity, params.project, spans]);
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
      />
    </Box>
  );
};
