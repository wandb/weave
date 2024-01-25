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
import React, {useEffect, useMemo, useState} from 'react';

import {parseRef} from '../../../../../../react';
import {flattenObject} from '../../../Browse2/browse2Util';
import {SpanWithFeedback} from '../../../Browse2/callTree';
import {
  buildTree,
  DataGridColumnGroupingModel,
} from '../../../Browse2/RunsTable';
import {SmallRef} from '../../../Browse2/SmallRef';
import {StyledDataGrid} from '../../StyledDataGrid';
import {renderCell} from '../util';

export type WFHighLevelPivotSpec = {
  rowDim: string;
  colDim: string;
};

export const PivotRunsView: React.FC<{
  loading: boolean;
  runs: SpanWithFeedback[];
  pivotSpec: Partial<WFHighLevelPivotSpec>;
  onPivotSpecChange: (spec: Partial<WFHighLevelPivotSpec>) => void;
}> = props => {
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
    if (options.length > 1) {
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
  }, [props]);

  return (
    <Box>
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
              size={'small'}
              renderInput={params => <TextField {...params} label="Rows" />}
              value={pivotRowDim ?? null}
              onChange={(event, newValue) => {
                props.onPivotSpecChange({
                  rowDim: newValue ?? undefined,
                });
              }}
              options={pivotRowOptions}
            />
          </FormControl>
        </ListItem>
        <ListItem>
          <FormControl fullWidth>
            <Autocomplete
              size={'small'}
              renderInput={params => <TextField {...params} label="Columns" />}
              value={pivotColDim ?? null}
              onChange={(event, newValue) => {
                props.onPivotSpecChange({
                  colDim: newValue ?? undefined,
                });
              }}
              options={pivotColOptions}
            />
          </FormControl>
        </ListItem>
      </Box>
      {props.pivotSpec.rowDim && props.pivotSpec.colDim ? (
        <PivotRunsTable {...props} />
      ) : (
        <>Please select pivot dimensions</>
      )}
    </Box>
  );
};

const PivotRunsTable: React.FC<{
  loading: boolean;
  runs: SpanWithFeedback[];
  pivotSpec: WFHighLevelPivotSpec;
}> = props => {
  const {pivotData, pivotColumns} = useMemo(() => {
    // TODO(tim/pivot_tables): Make this configurable and sort by timestamp!
    const aggregationFn = (internalRows: any[]) => {
      return internalRows[0];
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
          const value = cellParams.row[props.pivotSpec.rowDim];
          if (
            typeof value === 'string' &&
            value.startsWith('wandb-artifact:///')
          ) {
            return <SmallRef objRef={parseRef(value)} />;
          }
          return value;
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
      const outputGrouping = buildTree(outputOrder, col);
      outputGrouping.renderHeaderGroup = params => {
        const value = col;
        if (
          typeof value === 'string' &&
          value.startsWith('wandb-artifact:///')
        ) {
          return (
            <Box>
              <SmallRef objRef={parseRef(value)} />
            </Box>
          );
        }
        return value;
      };
      colGroupingModel.push(outputGrouping);
      for (const key of outputOrder) {
        cols.push({
          flex: 1,
          minWidth: 150,
          field: col + '.' + key,
          headerName: key.split('.').slice(-1)[0],
          // renderHeader: params => {
          //   console.log(params);
          //   if (params.field === col) {
          //     console.log(params);
          //   }
          //   // console.log('NO');
          // },
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

  // console.log({
  //   props,
  //   columns,
  //   pivotData,
  // });

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
        columnHeaderHeight={40}
        // apiRef={apiRef}
        // loading={loading}
        rows={pivotData}
        // density="compact"
        // initialState={initialState}
        rowHeight={38}
        columns={columns.cols}
        experimentalFeatures={{columnGrouping: true}}
        disableRowSelectionOnClick
        // rowSelectionModel={rowSelectionModel}
        initialState={{
          pinnedColumns: {
            left: [
              GRID_CHECKBOX_SELECTION_COL_DEF.field,
              props.pivotSpec.rowDim,
            ],
          },
        }}
        checkboxSelection={false}
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
        // isRowSelectable={(params: GridRowParams) =>
        //   rowSelectionModel.includes(params.id as string) ||
        //   rowSelectionModel.length < 2
        // }
        rowSelectionModel={rowSelectionModel}
        onRowSelectionModelChange={newSelection => {
          if (newSelection.length > 2) {
            // Limit to 2 selections for the time being.
            setSnackOpen(true);
            return;
          }
          setRowSelectionModel(newSelection as string[]);
        }}
      />
    </>
  );
};

const getValueAtNestedKey = (value: any, dimKey: string) => {
  dimKey.split('.').forEach(dim => {
    if (value != null) {
      value = value[dim];
    }
  });
  return value;
};
