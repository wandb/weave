import {
  Box,
  CircularProgress,
  FormControl,
  Snackbar,
  TextField,
  Typography,
} from '@mui/material';
import {Autocomplete, ListItem} from '@mui/material';
import {
  GRID_CHECKBOX_SELECTION_COL_DEF,
  GridColDef,
  GridColumnGroup,
} from '@mui/x-data-grid';
import _ from 'lodash';
import React, {
  ComponentProps,
  FC,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {useHistory} from 'react-router-dom';

import {flattenObject} from '../../../Browse2/browse2Util';
// import {SpanWithFeedback} from '../../../Browse2/callTree';
import {
  buildTree,
  DataGridColumnGroupingModel,
} from '../../../Browse2/RunsTable';
import {
  useClosePeek,
  usePeekLocation,
  useWeaveflowRouteContext,
  WeaveflowPeekContext,
} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {renderCell} from '../util';
import {CallSchema} from '../wfReactInterface/interface';
import {CenteredAnimatedLoader} from '../common/Loader';

export type WFHighLevelPivotSpec = {
  rowDim: string | null;
  colDim: string | null;
};

type PivotRunsTablePropsType = {
  loading: boolean;
  runs: CallSchema[];
  entity: string;
  project: string;
  colDimAtLeafMode?: boolean;
  showCompareButton?: boolean;
  hideControls?: boolean;
  extraDataGridProps?: ComponentProps<typeof StyledDataGrid>;
};

export const PivotRunsView: FC<
  PivotRunsTablePropsType & {
    pivotSpec: Partial<WFHighLevelPivotSpec>;
    onPivotSpecChange: (spec: Partial<WFHighLevelPivotSpec>) => void;
  }
> = props => {
  const pivotRowDim = props.pivotSpec.rowDim;
  const pivotColDim = props.pivotSpec.colDim;

  const [pivotRowOptions, setPivotRowOptions] = useState<string[]>([]);
  const [pivotColOptions, setPivotColOptions] = useState<string[]>([]);

  const runs = props.runs;

  const [effectivePivotSpec, setEffectivePivotSpec] = useState(props.pivotSpec);
  const currRowDim = effectivePivotSpec.rowDim;
  const currColDim = effectivePivotSpec.colDim;
  const onPivotSpecChange = props.onPivotSpecChange;
  useEffect(() => {
    if (runs.length === 0) {
      return;
    }
    const firstRun = runs[0];
    const options: string[] = [];
    Object.entries(firstRun.rawSpan.inputs).forEach(([key, value]) => {
      if (
        typeof value === 'string' &&
        value.startsWith('wandb-artifact:///') &&
        !key.startsWith('_')
      ) {
        options.push('inputs.' + key);
      }
    });
    setPivotRowOptions(options);
    setPivotColOptions(options);
    if (options.length > 0) {
      if (currRowDim == null && currColDim != null) {
        const rowOptions = options.filter(o => o !== currColDim);
        if (rowOptions.length > 0) {
          if (rowOptions.includes('inputs.example')) {
            setEffectivePivotSpec({
              rowDim: 'inputs.example',
              colDim: currColDim,
            });
          } else {
            setEffectivePivotSpec({
              rowDim: rowOptions[0],
              colDim: currColDim,
            });
          }
        }
      } else if (currRowDim != null && currColDim == null) {
        const colOptions = options.filter(o => o !== currRowDim);
        if (colOptions.length > 0) {
          setEffectivePivotSpec({
            rowDim: currRowDim,
            colDim: colOptions[0],
          });
        }
      } else if (currRowDim == null && currColDim == null) {
        if (options[0] === 'inputs.self') {
          setEffectivePivotSpec({
            rowDim: options[1],
            colDim: options[0],
          });
        } else {
          setEffectivePivotSpec({
            rowDim: options[0],
            colDim: options[1],
          });
        }
      }
    }
  }, [currColDim, currRowDim, onPivotSpecChange, runs]);

  return (
    <Box
      sx={{
        height: '100%',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}>
      <Box
        sx={{
          flex: '0 0 auto',
          width: '100%',
          transition: 'width 0.1s ease-in-out',
          display: props.hideControls ? 'none' : 'flex',
          flexDirection: 'row',
          overflowX: 'auto',
          overflowY: 'hidden',
          alignItems: 'center',
          gap: '8px',
          p: 1,
          '& li': {
            padding: 0,
            minWidth: '150px',
          },
          '& input, & label, & .MuiTypography-root': {
            fontSize: '0.875rem',
          },
        }}>
        <Typography
          style={{width: '38px', textAlign: 'center', flex: '0 0 auto'}}>
          Pivot
        </Typography>
        <ListItem>
          <FormControl fullWidth>
            <Autocomplete
              size="small"
              renderInput={params => <TextField {...params} label="Rows" />}
              value={pivotRowDim ?? null}
              onChange={(event, newValue) => {
                props.onPivotSpecChange({
                  colDim: pivotColDim,
                  rowDim: newValue ?? null,
                });
              }}
              options={pivotRowOptions}
              disableClearable={pivotRowDim != null}
            />
          </FormControl>
        </ListItem>
        <ListItem>
          <FormControl fullWidth>
            <Autocomplete
              size="small"
              renderInput={params => <TextField {...params} label="Columns" />}
              value={pivotColDim ?? null}
              onChange={(event, newValue) => {
                props.onPivotSpecChange({
                  colDim: newValue ?? null,
                  rowDim: pivotRowDim,
                });
              }}
              options={pivotColOptions}
              disableClearable={pivotColDim != null}
            />
          </FormControl>
        </ListItem>
      </Box>
      {effectivePivotSpec.rowDim != null &&
      effectivePivotSpec.colDim != null ? (
        <PivotRunsTable
          {...props}
          pivotSpec={
            effectivePivotSpec as {
              rowDim: string;
              colDim: string;
            }
          }
        />
      ) : (
        <CenteredAnimatedLoader />
        // <>Please select pivot dimensions</>
      )}
    </Box>
  );
};

const filterNulls = <T,>(arr: (T | null | undefined)[]): T[] => {
  return arr.filter(
    (e): e is Exclude<Exclude<typeof e, null>, undefined> => e !== null
  );
};

type PivotDataRowType = {
  id: string;
  rows: {[row: string]: string};
  cols: {[col: string]: CallSchema | null};
};

export const PivotRunsTable: FC<
  PivotRunsTablePropsType & {
    pivotSpec: {
      rowDim: string;
      colDim: string;
    };
  }
> = props => {
  const {isPeeking} = useContext(WeaveflowPeekContext);
  const {peekingRouter} = useWeaveflowRouteContext();
  const history = useHistory();

  const {pivotData, pivotColumns} = useMemo(() => {
    const aggregationFn = (internalRows: CallSchema[]): CallSchema | null => {
      if (internalRows.length === 0) {
        return null;
      }
      return _.sortBy(internalRows, r => -r.rawSpan.timestamp)[0];
    };

    // Step 1: Create a map of values
    const values: {[rowId: string]: {[colId: string]: CallSchema[]}} = {};
    const pivotColumnsInner: Set<string> = new Set();
    props.runs.forEach(r => {
      const rowValue = getValueAtNestedKey(r.rawSpan, props.pivotSpec.rowDim);
      const colValue = getValueAtNestedKey(r.rawSpan, props.pivotSpec.colDim);
      if (rowValue == null || colValue == null) {
        return;
      }
      pivotColumnsInner.add(colValue);
      if (!values[rowValue]) {
        values[rowValue] = {};
      }
      if (!values[rowValue][colValue]) {
        values[rowValue][colValue] = [];
      }
      values[rowValue][colValue].push(r);
    });

    // Step 2: Create a list of rows
    const rows: PivotDataRowType[] = [];
    Object.keys(values).forEach(rowKey => {
      const row: PivotDataRowType = {
        id: rowKey,
        rows: {},
        cols: {},
      };
      row.rows[props.pivotSpec.rowDim] = rowKey;
      Object.keys(values[rowKey]).forEach(colKey => {
        row.cols[colKey] = aggregationFn(values[rowKey][colKey]);
      });
      rows.push(row);
    });

    return {pivotData: rows, pivotColumns: pivotColumnsInner};
  }, [props.pivotSpec.colDim, props.pivotSpec.rowDim, props.runs]);

  const opsInPlay = useMemo(() => {
    return _.uniq(
      filterNulls(
        pivotData.flatMap(pivotRow =>
          Array.from(pivotColumns).map(col => pivotRow.cols[col]?.opVersionRef)
        )
      )
    );
  }, [pivotColumns, pivotData]);

  const usingLeafMode = props.colDimAtLeafMode && pivotColumns.size !== 1;

  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        flex: 1,
        minWidth: 175,
        field: props.pivotSpec.rowDim,
        headerName: props.pivotSpec.rowDim,
        renderCell: cellParams => {
          const row: PivotDataRowType = cellParams.row;
          return renderCell(row.rows[props.pivotSpec.rowDim]);
        },
      },
    ];

    const colGroupingModel: DataGridColumnGroupingModel = [];

    if (pivotData.length === 0) {
      return {cols: [], colGroupingModel: []};
    }

    if (!usingLeafMode) {
      pivotColumns.forEach(col => {
        // All output keys as we don't have the order key yet.
        const outputKeys: {[key: string]: true} = {};
        pivotData.forEach(pivotRow => {
          const pivotCol = pivotRow.cols[col];
          if (pivotCol) {
            for (const [k, v] of Object.entries(
              flattenObject(pivotCol.rawSpan.output!)
            )) {
              if (v != null && (!k.startsWith('_') || k === '_result')) {
                outputKeys[k] = true;
              }
            }
          }
        });

        const outputOrder = Object.keys(outputKeys);
        outputOrder.sort();
        const outputGrouping = buildTree(outputOrder, col);
        outputGrouping.renderHeaderGroup = params => {
          return renderCell(col);
        };
        colGroupingModel.push(outputGrouping);
        for (const key of outputOrder) {
          cols.push({
            flex: 1,
            minWidth: 100,
            field: col + '.' + key,
            headerName: key.split('.').slice(-1)[0],
            renderCell: cellParams => {
              const row: PivotDataRowType = cellParams.row;
              return renderCell(
                getValueAtNestedKey(row.cols[col]?.rawSpan.output, key)
              );
            },
          });
        }
      });
    } else {
      // Verify that each of the rows are from the same op
      if (opsInPlay.length !== 1) {
        throw new Error('All rows must be from the same op');
      }
      const op = opsInPlay[0];
      // All output keys as we don't have the order key yet.
      const outputKeys: {[key: string]: true} = {};
      pivotColumns.forEach(col => {
        pivotData.forEach(pivotRow => {
          const pivotCol = pivotRow.cols[col];
          if (pivotCol) {
            for (const [k, v] of Object.entries(
              flattenObject(pivotCol.rawSpan.output!)
            )) {
              if (v != null && (!k.startsWith('_') || k === '_result')) {
                outputKeys[k] = true;
              }
            }
          }
        });
      });

      const outputOrder = Object.keys(outputKeys).flatMap(key => {
        return Array.from(pivotColumns).map(col => key + '.' + col);
      });
      outputOrder.sort();
      const outputGrouping = buildTree(outputOrder, op);
      const outputGroups = outputGrouping.children as GridColumnGroup[];
      outputGroups.forEach(group => {
        colGroupingModel.push(group);
      });

      Object.keys(outputKeys).forEach(key => {
        pivotColumns.forEach(col => {
          cols.push({
            flex: 1,
            minWidth: 150,
            field: op + '.' + key + '.' + col,
            headerName: key.split('.').slice(-1)[0],
            renderHeader: params => {
              return renderCell(col);
            },
            renderCell: cellParams => {
              const row: PivotDataRowType = cellParams.row;
              return renderCell(
                getValueAtNestedKey(row.cols[col]?.rawSpan.output, key)
              );
            },
          });
        });
      });
    }

    return {cols, colGroupingModel};
  }, [
    opsInPlay,
    pivotColumns,
    pivotData,
    props.pivotSpec.rowDim,
    usingLeafMode,
  ]);

  const closePeek = useClosePeek();
  const [limitSnackOpen, setLimitSnackOpen] = useState(false);
  const [clickSnackOpen, setClickSnackOpen] = useState(false);
  const clickSnackEnabled = useRef(true);
  const openClickSnack = useCallback(() => {
    if (clickSnackEnabled.current) {
      setClickSnackOpen(true);
    }
  }, [clickSnackEnabled]);

  const [rowSelectionModel, setRowSelectionModel] = useState<string[]>([]);

  // Update row selection model from the URL.
  const peekLocation = usePeekLocation();
  useEffect(() => {
    if (!props.showCompareButton) {
      return;
    }
    const params = new URLSearchParams(peekLocation?.search ?? '');
    const entries = Array.from(params.entries());
    const searchDict = _.fromPairs(entries);
    const callIds: string[] = JSON.parse(searchDict.callIds ?? '[]');
    const rowIds = _.uniq(
      filterNulls(
        callIds.map(callId => {
          return pivotData.find(row => {
            return Array.from(pivotColumns).find(col => {
              return row.cols[col]?.callId === callId;
            });
          })?.id;
        })
      )
    );

    setRowSelectionModel(rowIds);
  }, [peekLocation, pivotColumns, pivotData, props.showCompareButton]);

  if (props.loading) {
    return <CenteredAnimatedLoader />;
  }

  return (
    <>
      <Snackbar
        open={limitSnackOpen}
        autoHideDuration={2000}
        onClose={() => {
          setLimitSnackOpen(false);
        }}
        message="Only 2 rows can be selected at a time."
      />
      <Snackbar
        open={clickSnackOpen}
        autoHideDuration={2000}
        onClose={() => {
          setClickSnackOpen(false);
        }}
        message="Double click to view source call."
      />
      <StyledDataGrid
        key={props.pivotSpec.rowDim + props.pivotSpec.colDim}
        columnHeaderHeight={40}
        rows={pivotData}
        rowHeight={38}
        columns={columns.cols}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
        initialState={{
          pinnedColumns: {
            left: [
              GRID_CHECKBOX_SELECTION_COL_DEF.field,
              props.pivotSpec.rowDim,
            ],
          },
        }}
        checkboxSelection={!isPeeking && props.showCompareButton}
        columnGroupingModel={columns.colGroupingModel}
        rowSelectionModel={rowSelectionModel}
        onCellClick={params => {
          if (
            params.field === '__check__' ||
            params.field === props.pivotSpec.rowDim
          ) {
            return;
          }
          clickSnackEnabled.current = true;
          setTimeout(() => {
            openClickSnack();
          }, 250);
        }}
        onCellDoubleClick={params => {
          if (
            params.field === '__check__' ||
            params.field === props.pivotSpec.rowDim
          ) {
            return;
          }
          clickSnackEnabled.current = false;
          const fieldParts = params.field.split('.');
          const col = usingLeafMode
            ? fieldParts[fieldParts.length - 1]
            : fieldParts[0];
          const row: PivotDataRowType = params.row;
          const cellSpan = row.cols[col];
          if (!cellSpan) {
            return;
          }
          history.push(
            peekingRouter.callUIUrl(
              props.entity,
              props.project,
              '',
              cellSpan.callId
            )
          );
        }}
        onRowSelectionModelChange={newSelection => {
          if (newSelection.length > 2) {
            // Limit to 2 selections for the time being.
            setLimitSnackOpen(true);
            return;
          }

          setRowSelectionModel(newSelection as string[]);
          if (newSelection.length === 0) {
            closePeek();
            return;
          }

          const callIds: string[] = _.uniq(
            newSelection.flatMap(id => {
              return pivotData.flatMap(row => {
                if (row.id !== id) {
                  return [];
                }
                return Array.from(pivotColumns)
                  .map(col => {
                    return row.cols[col]?.callId;
                  })
                  .filter(maybeId => maybeId != null) as string[];
              });
            })
          );

          history.push(
            peekingRouter.compareCallsUIUrl(
              props.entity,
              props.project,
              callIds,
              props.pivotSpec.rowDim,
              props.pivotSpec.colDim
            )
          );
        }}
        sx={{
          '& .MuiDataGrid-virtualScrollerRenderZone > div > .MuiDataGrid-cell':
            {
              cursor: 'pointer',
            },
          ...(props.extraDataGridProps?.sx ?? {}),
        }}
        {...props.extraDataGridProps}
      />
    </>
  );
};

export const getValueAtNestedKey = (value: any, dimKey: string) => {
  dimKey.split('.').forEach(dim => {
    if (value != null) {
      value = value[dim];
    }
  });
  return value;
};
