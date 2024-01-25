import {Box, CircularProgress, Snackbar} from '@material-ui/core';
import {GRID_CHECKBOX_SELECTION_COL_DEF, GridColDef} from '@mui/x-data-grid';
import _ from 'lodash';
import React, {useMemo, useState} from 'react';

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

export const PivotRunsTable: React.FC<{
  loading: boolean;
  runs: SpanWithFeedback[];
  rowsDim?: string | null;
  colsDim?: string | null;
}> = props => {
  const {pivotData, pivotColumns} = useMemo(() => {
    if (props.rowsDim == null || props.colsDim == null) {
      return {pivotData: [], pivotColumns: new Set<string>()};
    }

    // TODO(tim/pivot_tables): Make this configurable and sort by timestamp!
    const aggregation = (values: any[]) => {
      return values[0];
    };

    // Step 1: Create a map of values
    const values: {[rowId: string]: {[colId: string]: any[]}} = {};
    const pivotColumns: Set<string> = new Set();
    props.runs.forEach(r => {
      const rowValue = getValueAtNestedKey(r, props.rowsDim!);
      const colValue = getValueAtNestedKey(r, props.colsDim!);
      if (rowValue == null || colValue == null) {
        return;
      }
      pivotColumns.add(colValue);
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
      row[props.rowsDim!] = rowKey;
      Object.keys(values[rowKey]).forEach(colKey => {
        row[colKey] = aggregation(values[rowKey][colKey]);
      });
      rows.push(row);
    });

    return {pivotData: rows, pivotColumns};
  }, [props.colsDim, props.rowsDim, props.runs]);

  const columns = useMemo(() => {
    const cols: GridColDef[] = [
      {
        flex: 1,
        minWidth: 175,
        field: props.rowsDim!,
        headerName: props.rowsDim!,
        renderCell: cellParams => {
          const value = cellParams.row[props.rowsDim!];
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
      let outputKeys: {[key: string]: true} = {};
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
              getValueAtNestedKey(cellParams.row[col]?.['output'], key)
            );
          },
        });
      }
    });

    return {cols, colGroupingModel};
  }, [pivotColumns, pivotData, props.rowsDim]);

  const [rowSelectionModel, setRowSelectionModel] = useState<string[]>([]);
  const [snackOpen, setSnackOpen] = useState(false);
  if (props.loading) {
    return <CircularProgress />;
  }
  if (props.rowsDim == null || props.colsDim == null) {
    return <>Call to action: Select dimensions</>;
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
            left: [GRID_CHECKBOX_SELECTION_COL_DEF.field, props.rowsDim!],
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
