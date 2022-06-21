import {useMemo} from 'react';
import * as Types from '@wandb/cg/browser/model/types';
import * as Table from './tableState';
import * as Op from '@wandb/cg/browser/ops';
import {usePanelContext} from '../PanelContext';
import {useRefineExpressionsEffect} from '../panellib/libexp';

// This refines all table state expressions when their input variable values
// change. This is is complicated by the fact that grouped v. ungrouped
// columns use different nodes for their row variables. If we do Tim's
// change to separate pre & post group select functions in the UI, this
// function will get much simpler and can basically just be a call to
// useRefineExpressionsEffect
export function useTableStateWithRefinedExpressions(
  inputNode: Types.Node,
  tableState: Table.TableState
): {isRefining: boolean; tableState: Table.TableState} {
  let {frame} = usePanelContext();
  frame = useMemo(() => ({...frame}), [frame]);
  const rowsNode = useMemo(
    () =>
      Table.getRowsNode(
        tableState.preFilterFunction,
        tableState.groupBy,
        tableState.columnSelectFunctions,
        tableState.columnNames,
        tableState.order,
        tableState.sort,
        inputNode
      ),
    [
      inputNode,
      tableState.preFilterFunction,
      tableState.groupBy,
      tableState.columnSelectFunctions,
      tableState.columnNames,
      tableState.order,
      tableState.sort,
    ]
  );

  // Split expressions for grouped and ungrouped columns
  const ungroupedCols = useMemo(
    () => tableState.order.filter(colId => !tableState.groupBy.includes(colId)),
    [tableState.groupBy, tableState.order]
  );
  const groupedColExpressions = useMemo(
    () => tableState.groupBy.map(id => tableState.columnSelectFunctions[id]),
    [tableState.columnSelectFunctions, tableState.groupBy]
  );
  const ungroupedColExpressions = useMemo(
    () => ungroupedCols.map(id => tableState.columnSelectFunctions[id]),
    [tableState.columnSelectFunctions, ungroupedCols]
  );

  // Make two frames, one for grouped columns, one for ungrouped (since they
  // use a different row variable)
  const groupedCellFrame = useMemo(() => {
    return tableState.groupBy.length > 0
      ? Table.getCellFrame(
          inputNode,
          rowsNode,
          frame,
          tableState.groupBy,
          tableState.columnSelectFunctions,
          tableState.groupBy[0]
        )
      : frame;
  }, [
    rowsNode,
    frame,
    inputNode,
    tableState.groupBy,
    tableState.columnSelectFunctions,
  ]);
  const ungroupedCellFrame = useMemo(() => {
    return ungroupedCols.length > 0
      ? Table.getCellFrame(
          inputNode,
          rowsNode,
          frame,
          tableState.groupBy,
          tableState.columnSelectFunctions,
          ungroupedCols[0]
        )
      : frame;
  }, [
    rowsNode,
    frame,
    inputNode,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    ungroupedCols,
  ]);

  // Refine our grouped & ungrouped columns if their frame variables have
  // changed
  const groupedSelectFunctions = useRefineExpressionsEffect(
    Object.values(groupedColExpressions),
    groupedCellFrame
  );
  const ungroupedSelectFunctions = useRefineExpressionsEffect(
    Object.values(ungroupedColExpressions),
    ungroupedCellFrame
  );

  // Stick the expressions back in config so downstream consumers
  // of config get the right thing.
  return useMemo(() => {
    const newColSelectFunctions: typeof tableState.columnSelectFunctions = {};
    tableState.groupBy.forEach(
      (k, i) =>
        (newColSelectFunctions[k] =
          groupedSelectFunctions.refinedExpressions[i])
    );
    ungroupedCols.forEach(
      (k, i) =>
        (newColSelectFunctions[k] =
          ungroupedSelectFunctions.refinedExpressions[i])
    );
    return {
      isRefining:
        groupedSelectFunctions.isRefining ||
        ungroupedSelectFunctions.isRefining,
      tableState: {
        ...tableState,
        columnSelectFunctions: {
          ...tableState.columnSelectFunctions,
          ...newColSelectFunctions,
        },
      },
    };
  }, [
    tableState,
    groupedSelectFunctions,
    ungroupedSelectFunctions,
    ungroupedCols,
  ]);
}
