import {Alert, Box, Button, Typography} from '@mui/material';
import {
  DataGridPro as DataGrid,
  DataGridPro,
  GridColDef,
  GridColumnGroup,
  GridRowSelectionModel,
  useGridApiRef,
} from '@mui/x-data-grid-pro';
import {monthRoundedTime} from '@wandb/weave/time';
import * as _ from 'lodash';
import React, {
  ComponentProps,
  FC,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useParams} from 'react-router-dom';

import {MOON_250} from '../../../../common/css/color.styles';
import {A, TargetBlank} from '../../../../common/util/links';
import {Timestamp} from '../../../Timestamp';
import {CategoryChip} from '../Browse3/pages/common/CategoryChip';
import {CallLink, OpVersionLink} from '../Browse3/pages/common/Links';
import {StatusChip} from '../Browse3/pages/common/StatusChip';
import {renderCell, useURLSearchParamsDict} from '../Browse3/pages/util';
import {useMaybeWeaveflowORMContext} from '../Browse3/pages/wfInterface/context';
import {StyledDataGrid} from '../Browse3/StyledDataGrid';
import {flattenObject} from './browse2Util';
import {SpanWithFeedback} from './callTree';
import {Browse2RootObjectVersionItemParams} from './CommonLib';
import {
  computeTableStats,
  getInputColumns,
  useColumnVisibility,
} from './tableStats';

export type DataGridColumnGroupingModel = Exclude<
  ComponentProps<typeof DataGrid>['columnGroupingModel'],
  undefined
>;

function addToTree(
  node: GridColumnGroup,
  fields: string[],
  fullPath: string,
  depth: number
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
    if ('groupId' in child && child.headerName === fields[0]) {
      addToTree(child as GridColumnGroup, fields.slice(1), fullPath, depth + 1);
      return;
    }
  }

  const newNode: GridColumnGroup = {
    headerName: fields[0],
    groupId: fullPath
      .split('.')
      .slice(0, depth + 2)
      .join('.'),
    children: [],
  };
  node.children.push(newNode);
  addToTree(newNode, fields.slice(1), fullPath, depth + 1);
}

export function buildTree(
  strings: string[],
  rootGroupName: string
): GridColumnGroup {
  const root: GridColumnGroup = {groupId: rootGroupName, children: []};

  for (const str of strings) {
    const fields = str.split('.');
    addToTree(root, fields, rootGroupName + '.' + str, 0);
  }

  return root;
}

export const RunsTable: FC<{
  loading: boolean;
  spans: SpanWithFeedback[];
  clearFilters?: null | (() => void);
  ioColumnsOnly?: boolean;
}> = ({loading, spans, clearFilters, ioColumnsOnly}) => {
  const showIO = true;
  const isSingleOpVersion = useMemo(() => {
    return _.uniq(spans.map(span => span.name)).length === 1;
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
        latency: call.summary.latency_s,
        ..._.mapValues(
          _.mapKeys(
            _.omitBy(args, v => v == null),
            (v, k) => {
              return 'input.' + k;
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
  const tableStats = useMemo(() => {
    return computeTableStats(tableData);
  }, [tableData]);
  const {allShown, columnVisibilityModel, forceShowAll, setForceShowAll} =
    useColumnVisibility(tableStats);
  const showVisibilityAlert = !isSingleOpVersion && !allShown && !forceShowAll;

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
        field: 'span_id',
        headerName: 'Trace',
        width: 75,
        minWidth: 75,
        maxWidth: 75,
        hideable: false,
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
      {
        field: 'status_code',
        headerName: 'Status',
        sortable: false,
        disableColumnMenu: true,
        resizable: false,
        width: 70,
        minWidth: 70,
        maxWidth: 70,
        renderCell: cellParams => {
          return (
            <div style={{margin: 'auto'}}>
              <StatusChip value={cellParams.row.status_code} iconOnly />
            </div>
          );
        },
      },
      ...(orm && !ioColumnsOnly
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
                return (
                  <OpVersionLink
                    entityName={opVersion.entity()}
                    projectName={opVersion.project()}
                    opName={opVersion.op().name()}
                    version={opVersion.version()}
                    versionIndex={opVersion.versionIndex()}
                  />
                );
              },
            },
          ]
        : []),
      ...(orm && !ioColumnsOnly
        ? [
            {
              field: 'opCategory',
              headerName: 'Category',
              width: 100,
              minWidth: 100,
              maxWidth: 100,
              renderCell: (cellParams: any) => {
                return (
                  cellParams.value && <CategoryChip value={cellParams.value} />
                );
              },
            },
          ]
        : []),
      ...(!ioColumnsOnly
        ? [
            {
              field: 'timestampMs',
              headerName: 'Called',
              width: 100,
              minWidth: 100,
              maxWidth: 100,
              renderCell: (cellParams: any) => {
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
              renderCell: (cellParams: any) => {
                return monthRoundedTime(cellParams.row.latency);
              },
            },
          ]
        : []),
    ];
    const colGroupingModel: DataGridColumnGroupingModel = [];
    const row0 = spans[0];
    if (row0 == null) {
      return {cols: [], colGroupingModel: []};
    }

    let attributesKeys: {[key: string]: true} = {};
    spans.forEach(span => {
      for (const [k, v] of Object.entries(
        flattenObject(span.attributes ?? {})
      )) {
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
              return renderCell(cellParams.row['attributes.' + key]);
            },
          });
        }
      }

      const inputOrder = !isSingleOpVersion
        ? getInputColumns(tableStats)
        : row0.inputs._arg_order ??
          Object.keys(_.omitBy(row0.inputs, v => v == null)).filter(
            k => !k.startsWith('_')
          );
      const inputGroup: Exclude<
        ComponentProps<typeof DataGrid>['columnGroupingModel'],
        undefined
      >[number] = {
        groupId: 'inputs',
        children: [],
      };
      for (const key of inputOrder) {
        cols.push({
          flex: 1,
          minWidth: 150,
          field: 'input.' + key,
          headerName: key,
          renderCell: cellParams => {
            const k = 'input.' + key;
            if (k in cellParams.row) {
              return renderCell(cellParams.row[k]);
            }
            return <NotApplicable />;
          },
        });
        inputGroup.children.push({field: 'input.' + key});
      }
      colGroupingModel.push(inputGroup);

      // All output keys as we don't have the order key yet.
      let outputKeys: {[key: string]: true} = {};
      spans.forEach(span => {
        for (const [k, v] of Object.entries(flattenObject(span.output ?? {}))) {
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
            const k = 'output.' + key;
            if (k in cellParams.row) {
              return renderCell(cellParams.row[k]);
            }
            return <NotApplicable />;
          },
        });
      }

      let feedbackKeys: {[key: string]: true} = {};
      spans.forEach(span => {
        for (const [k, v] of Object.entries(
          flattenObject(span.feedback ?? {})
        )) {
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
            return renderCell(cellParams.row['feedback.' + key]);
          },
        });
      }
    }

    return {cols, colGroupingModel};
  }, [
    orm,
    ioColumnsOnly,
    showIO,
    spans,
    params.entity,
    params.project,
    isSingleOpVersion,
    tableStats,
  ]);
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
  const initialState: ComponentProps<typeof DataGridPro>['initialState'] =
    useMemo(() => {
      if (loading) {
        return undefined;
      }
      return {
        pinnedColumns: {left: ['span_id']},
        sorting: {
          sortModel: [{field: 'timestampMs', sort: 'desc'}],
        },
        columns: {
          columnVisibilityModel,
        },
      };
    }, [loading, columnVisibilityModel]);

  // This is a workaround.
  // initialState won't take effect if columns are not set.
  // see https://github.com/mui/mui-x/issues/6206
  useEffect(() => {
    if (columns != null && initialState != null) {
      apiRef.current.restoreState(initialState);
    }
  }, [columns, initialState, apiRef]);

  return (
    <>
      {showVisibilityAlert && (
        <Alert
          severity="info"
          action={
            <Button
              color="inherit"
              size="small"
              onClick={() => setForceShowAll(true)}>
              Show all
            </Button>
          }>
          Columns having many empty values have been hidden.
        </Alert>
      )}
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
        slots={{
          noRowsOverlay: () => {
            return (
              <Box
                sx={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                }}>
                <Typography color="textSecondary">
                  No calls found.{' '}
                  {clearFilters != null ? (
                    <>
                      Try{' '}
                      <A
                        onClick={() => {
                          clearFilters();
                        }}>
                        clearing the filters
                      </A>{' '}
                      or l
                    </>
                  ) : (
                    'L'
                  )}
                  earn more about how to log calls by visiting{' '}
                  <TargetBlank href="https://wandb.me/weave">
                    the docs
                  </TargetBlank>
                  .
                </Typography>
              </Box>
            );
          },
        }}
      />
    </>
  );
};

const NotApplicable = () => {
  return <Box sx={{color: MOON_250}}>N/A</Box>;
};
