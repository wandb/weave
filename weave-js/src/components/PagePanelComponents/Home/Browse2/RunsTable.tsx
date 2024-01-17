import {Chip} from '@mui/material';
import {
  DataGridPro as DataGrid,
  DataGridPro,
  GridColDef,
  GridColumnGroup,
  GridRowSelectionModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {parseRef} from '@wandb/weave/react';
import {monthRoundedTime} from '@wandb/weave/time';
import * as _ from 'lodash';
import React, {FC, useEffect, useMemo, useRef, useState} from 'react';
import {useParams} from 'react-router-dom';

import {Timestamp} from '../../../Timestamp';
import {CallStatusCodeChip} from '../Browse3/pages/common/CallStatusCodeChip';
import {CallLink, opVersionText} from '../Browse3/pages/common/Links';
import {useURLSearchParamsDict} from '../Browse3/pages/util';
import {useMaybeWeaveflowORMContext} from '../Browse3/pages/wfInterface/context';
import {StyledDataGrid} from '../Browse3/StyledDataGrid';
import {flattenObject} from './browse2Util';
import {SpanWithFeedback} from './callTree';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {SmallRef} from './SmallRef';

type DataGridColumnGroupingModel = Exclude<
  React.ComponentProps<typeof DataGrid>['columnGroupingModel'],
  undefined
>;

function addToTree(
  node: GridColumnGroup,
  fields: string[],
  fullPath: string
): void {
  if (!fields.length) {
    return;
  }

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
  const showIO = useMemo(() => {
    return Array.from(new Set(spans.map(span => span.name))).length === 1;
  }, [spans]);
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
  const orm = useMaybeWeaveflowORMContext();
  const params = useParams<Browse2RootObjectVersionItemParams>();
  const tableData = useMemo(() => {
    return spans.map((call: SpanWithFeedback) => {
      const ormCall = orm?.projectConnection.call(call.span_id);
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
        ormCall,
        loading,
        opVersion: ormCall?.opVersion()?.op()?.name(),
        isRoot: ormCall?.parentCall() == null,
        opCategory: ormCall?.opVersion()?.opCategory(),
        trace_id: call.trace_id,
        status_code: call.status_code,
        timestampMs: call.timestamp,
        latency: monthRoundedTime(call.summary.latency_s),
        ..._.mapValues(
          _.mapKeys(
            _.omitBy(args, v => v == null),
            (v, k) => {
              return 'input_' + k;
            }
          ),
          v =>
            typeof v === 'string' || typeof v === 'number'
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
            typeof v === 'string' || typeof v === 'number'
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
  }, [orm?.projectConnection, spans, loading]);

  // Highlight table row if it matches peek drawer.
  const query = useURLSearchParamsDict();
  const {peekPath} = query;
  const peekId = peekPath ? peekPath.split('/').pop() : null;
  const rowIds = useMemo(() => {
    return tableData.map(row => row.id);
  }, [tableData]);
  const [rowSelectionModel, setRowSelectionModel] =
    useState<GridRowSelectionModel>([]);
  useEffect(() => {
    if (rowIds.length === 0) {
      // Data may have not loaded
      return;
    }
    if (peekId == null) {
      // No peek drawer, clear any selection
      setRowSelectionModel([]);
    } else {
      // If peek drawer matches a row, select it.
      // If not, don't modify selection.
      if (rowIds.includes(peekId)) {
        setRowSelectionModel([peekId]);
      }
    }
  }, [rowIds, peekId]);

  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        field: 'status_code',
        headerName: '',
        width: 40,
        minWidth: 40,
        maxWidth: 40,
        sortable: false,
        disableColumnMenu: true,
        resizable: false,
        renderCell: cellParams => {
          return <CallStatusCodeChip statusCode={cellParams.row.status_code} />;
        },
      },
      {
        field: 'span_id',
        headerName: 'ID',
        width: 75,
        minWidth: 75,
        maxWidth: 75,
        renderCell: rowParams => {
          // return truncateID(rowParams.row.id);
          return (
            <CallLink
              entityName={params.entity}
              projectName={params.project}
              callId={rowParams.row.id}
            />
          );
        },
      },
      ...(orm
        ? [
            {
              flex: !showIO ? 1 : undefined,
              field: 'opVersion',
              headerName: 'Op',
              renderCell: (rowParams: any) => {
                const opVersion = rowParams.row.ormCall?.opVersion();
                if (opVersion == null) {
                  return rowParams.row.ormCall?.spanName();
                }
                return opVersionText(
                  rowParams.row.ormCall?.spanName(),
                  opVersion.versionIndex()
                );
              },
            },
          ]
        : []),
      ...(orm
        ? [
            {
              field: 'opCategory',
              headerName: 'Category',
              width: 100,
              minWidth: 100,
              maxWidth: 100,
              renderCell: (cellParams: any) => {
                if (cellParams.value == null) {
                  return '';
                }
                const color = {
                  train: 'success',
                  predict: 'info',
                  score: 'error',
                  evaluate: 'warning',
                  // 'tune': 'warning',
                }[cellParams.row.opCategory + ''];
                return (
                  <Chip
                    sx={{height: '20px', lineHeight: 2}}
                    label={cellParams.row.opCategory}
                    size="small"
                    color={color as any}
                  />
                );
              },
            },
          ]
        : []),

      {
        field: 'timestampMs',
        headerName: 'Called',
        width: 100,
        minWidth: 100,
        maxWidth: 100,
        renderCell: cellParams => {
          return (
            <Timestamp
              value={cellParams.row.timestampMs / 1000}
              format="relative"
            />
          );
        },
      },

      {
        field: 'latency',
        headerName: 'Latency',
        width: 100,
        minWidth: 100,
        maxWidth: 100,
        // flex: !showIO ? 1 : undefined,
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

    if (showIO) {
      const attributesOrder = Object.keys(attributesKeys);
      const attributesGrouping = buildTree(attributesOrder, 'attributes');
      colGroupingModel.push(attributesGrouping);
      for (const key of attributesOrder) {
        if (!key.startsWith('_')) {
          cols.push({
            flex: 1,
            minWidth: 150,
            field: 'attributes.' + key,
            headerName: key.split('.').slice(-1)[0],
            renderCell: cellParams => {
              if (
                typeof cellParams.row['attributes.' + key] === 'string' &&
                cellParams.row['attributes.' + key].startsWith(
                  'wandb-artifact:///'
                )
              ) {
                return (
                  <SmallRef
                    objRef={parseRef(cellParams.row['attributes.' + key])}
                  />
                );
              }
              return cellParams.row['attributes.' + key];
            },
          });
        }
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
          flex: 1,
          minWidth: 150,
          field: 'input_' + key,
          headerName: key,
          renderCell: cellParams => {
            if (
              typeof cellParams.row['input_' + key] === 'string' &&
              cellParams.row['input_' + key].startsWith('wandb-artifact:///')
            ) {
              return (
                <SmallRef objRef={parseRef(cellParams.row['input_' + key])} />
              );
            }
            return cellParams.row['input_' + key];
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
          flex: 1,
          minWidth: 150,
          field: 'output.' + key,
          headerName: key.split('.').slice(-1)[0],
          renderCell: cellParams => {
            if (
              typeof cellParams.row['output.' + key] === 'string' &&
              cellParams.row['output.' + key].startsWith('wandb-artifact:///')
            ) {
              return (
                <SmallRef objRef={parseRef(cellParams.row['output.' + key])} />
              );
            }
            return cellParams.row['output.' + key];
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
          flex: 1,
          minWidth: 150,
          field: 'feedback.' + key,
          headerName: key.split('.').slice(-1)[0],
          renderCell: cellParams => {
            if (
              typeof cellParams.row['feedback.' + key] === 'string' &&
              cellParams.row['feedback.' + key].startsWith('wandb-artifact:///')
            ) {
              return (
                <SmallRef
                  objRef={parseRef(cellParams.row['feedback.' + key])}
                />
              );
            }
            return cellParams.row['feedback.' + key];
          },
        });
      }
    }

    return {cols, colGroupingModel};
  }, [orm, params.entity, params.project, showIO, spans]);
  const autosized = useRef(false);
  // const {peekingRouter} = useWeaveflowRouteContext();
  // const history = useHistory();
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
  const initialState: React.ComponentProps<typeof DataGridPro>['initialState'] =
    useMemo(() => {
      if (loading) {
        return undefined;
      }
      return {
        sorting: {
          sortModel: [{field: 'timestampMs', sort: 'desc'}],
        },
      };
    }, [loading]);

  return (
    <StyledDataGrid
      columnHeaderHeight={40}
      apiRef={apiRef}
      loading={loading}
      rows={tableData}
      // density="compact"
      initialState={initialState}
      rowHeight={38}
      columns={columns.cols}
      experimentalFeatures={{columnGrouping: true}}
      disableRowSelectionOnClick
      rowSelectionModel={rowSelectionModel}
      columnGroupingModel={columns.colGroupingModel}
      // onRowClick={({id}) => {
      //   history.push(
      //     peekingRouter.callUIUrl(
      //       params.entity,
      //       params.project,
      //       '',
      //       id as string
      //     )
      //   );
      // }}
    />
    // </Box>
  );
};
