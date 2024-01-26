import {
  Box,
  CircularProgress,
  FormControl,
  Snackbar,
  TextField,
  Typography,
} from '@mui/material';
import {Autocomplete, ListItem} from '@mui/material';
import {GRID_CHECKBOX_SELECTION_COL_DEF, GridColDef} from '@mui/x-data-grid';
import _ from 'lodash';
import React, {useContext, useEffect, useMemo, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';

import {parseRef} from '../../../../../../react';
import {flattenObject} from '../../../Browse2/browse2Util';
import {Call, SpanWithFeedback} from '../../../Browse2/callTree';
import {
  buildTree,
  DataGridColumnGroupingModel,
} from '../../../Browse2/RunsTable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {useWeaveflowRouteContext, WeaveflowPeekContext} from '../../context';
import {StyledDataGrid} from '../../StyledDataGrid';
import {renderCell} from '../util';

export type WFHighLevelPivotSpec = {
  rowDim: string | null;
  colDim: string | null;
};

type PivotRunsTablePropsType = {
  loading: boolean;
  runs: Call[];
  entity: string;
  project: string;
  colDimAtLeafMode?: boolean;
  showCompareButton?: boolean;
  extraDataGridProps?: React.ComponentProps<typeof StyledDataGrid>;
};

export const PivotRunsView: React.FC<
  PivotRunsTablePropsType & {
    pivotSpec: Partial<WFHighLevelPivotSpec>;
    onPivotSpecChange: (spec: Partial<WFHighLevelPivotSpec>) => void;
  }
> = props => {
  const pivotRowDim = props.pivotSpec.rowDim;
  const pivotColDim = props.pivotSpec.colDim;

  const [pivotRowOptions, setPivotRowOptions] = useState<string[]>([]);
  const [pivotColOptions, setPivotColOptions] = useState<string[]>([]);

  useEffect(() => {
    const runs = props.runs;
    if (runs.length === 0) {
      return;
    }
    const firstRun = runs[0];
    const options: string[] = [];
    Object.entries(firstRun.inputs).forEach(([key, value]) => {
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
      const currRowDim = props.pivotSpec.rowDim;
      const currColDim = props.pivotSpec.colDim;

      if (currRowDim == null && currColDim != null) {
        const rowOptions = options.filter(o => o !== currColDim);
        if (rowOptions.length > 0) {
          if (rowOptions.includes('inputs.example')) {
            props.onPivotSpecChange({
              rowDim: 'inputs.example',
              colDim: currColDim,
            });
          } else {
            props.onPivotSpecChange({
              rowDim: rowOptions[0],
              colDim: currColDim,
            });
          }
        }
      } else if (currRowDim != null && currColDim == null) {
        const colOptions = options.filter(o => o !== currRowDim);
        if (colOptions.length > 0) {
          props.onPivotSpecChange({
            rowDim: currRowDim,
            colDim: colOptions[0],
          });
        }
      } else if (currRowDim == null && currColDim == null) {
        if (options[0] === 'inputs.self') {
          props.onPivotSpecChange({
            rowDim: options[1],
            colDim: options[0],
          });
        } else {
          props.onPivotSpecChange({
            rowDim: options[0],
            colDim: options[1],
          });
        }
      }
    }
  }, [props]);

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
          display: 'flex',
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
              value={pivotRowDim ?? ''}
              onChange={(event, newValue) => {
                props.onPivotSpecChange({
                  colDim: pivotColDim,
                  rowDim: newValue ?? null,
                });
              }}
              options={pivotRowOptions}
              disableClearable
            />
          </FormControl>
        </ListItem>
        <ListItem>
          <FormControl fullWidth>
            <Autocomplete
              size="small"
              renderInput={params => <TextField {...params} label="Columns" />}
              value={pivotColDim ?? ''}
              onChange={(event, newValue) => {
                props.onPivotSpecChange({
                  colDim: newValue ?? null,
                  rowDim: pivotRowDim,
                });
              }}
              options={pivotColOptions}
              disableClearable
            />
          </FormControl>
        </ListItem>
      </Box>
      {props.pivotSpec.rowDim && props.pivotSpec.colDim ? (
        <PivotRunsTable
          {...props}
          pivotSpec={
            props.pivotSpec as {
              rowDim: string;
              colDim: string;
            }
          }
        />
      ) : (
        <>Please select pivot dimensions</>
      )}
    </Box>
  );
};

export const PivotRunsTable: React.FC<
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
    const aggregationFn = (internalRows: SpanWithFeedback[]) => {
      if (internalRows.length === 0) {
        return null;
      }
      return _.sortBy(internalRows, r => -r.timestamp)[0];
    };

    // Step 1: Create a map of values
    const values: {[rowId: string]: {[colId: string]: any[]}} = {};
    const pivotColumnsInner: Set<string> = new Set();
    props.runs.forEach(r => {
      const rowValue = getValueAtNestedKey(r, props.pivotSpec.rowDim);
      const colValue = getValueAtNestedKey(r, props.pivotSpec.colDim);
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
    const rows: Array<{[col: string]: any}> = [];
    Object.keys(values).forEach(rowKey => {
      const row: {[col: string]: any} = {
        id: rowKey,
      };
      row[props.pivotSpec.rowDim] = rowKey;
      Object.keys(values[rowKey]).forEach(colKey => {
        row[colKey] = aggregationFn(values[rowKey][colKey]);
      });
      rows.push(row);
    });

    return {pivotData: rows, pivotColumns: pivotColumnsInner};
  }, [props.pivotSpec.colDim, props.pivotSpec.rowDim, props.runs]);

  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        flex: 1,
        minWidth: 175,
        field: props.pivotSpec.rowDim,
        headerName: props.pivotSpec.rowDim,
        renderCell: cellParams => {
          return renderCell(cellParams.row[props.pivotSpec.rowDim]);
        },
      },
    ];

    const colGroupingModel: DataGridColumnGroupingModel = [];

    if (pivotData.length === 0) {
      return {cols: [], colGroupingModel: []};
    }
    pivotColumns.forEach(col => {
      // All output keys as we don't have the order key yet.
      const outputKeys: {[key: string]: true} = {};
      pivotData.forEach(pivotRow => {
        if (pivotRow[col]) {
          for (const [k, v] of Object.entries(
            flattenObject(pivotRow[col].output!)
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
            return renderCell(
              getValueAtNestedKey(cellParams.row[col]?.output, key)
            );
          },
        });
      }
    });

    return {cols, colGroupingModel};
  }, [pivotColumns, pivotData, props.pivotSpec.rowDim]);

  const [rowSelectionModel, setRowSelectionModel] = useState<string[]>([]);
  const [snackOpen, setSnackOpen] = useState(false);

  if (props.loading) {
    return <CircularProgress />;
  }

  return (
    <>
      <Snackbar
        open={snackOpen}
        autoHideDuration={2000}
        onClose={() => {
          setSnackOpen(false);
        }}
        message="Only 2 rows can be selected at a time."
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
        onRowSelectionModelChange={newSelection => {
          if (newSelection.length > 2) {
            // Limit to 2 selections for the time being.
            setSnackOpen(true);
            return;
          }
          setRowSelectionModel(newSelection as string[]);

          if (newSelection.length !== 2) {
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
                    return row[col]?.span_id;
                  })
                  .filter(id => id != null);
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
