import {useWeaveRefinementInReactHooksDisabled} from '@wandb/weave/context';
import {Node, pushFrame, Stack, WeaveInterface} from '@wandb/weave/core';

import {
  makePromiseUsable,
  refineExpressions,
  vectorizePromiseFn,
} from './hooks';
import * as Table from './tableState';

// This refines all table state expressions when their input variable values
// change. This is is complicated by the fact that grouped v. ungrouped
// columns use different nodes for their row variables. If we do Tim's
// change to separate pre & post group select functions in the UI, this
// function will get much simpler and can basically just be a call to
// useRefineExpressionsEffect

async function refineTableStateExpressions(
  tableState: Table.TableState,
  inputNode: Node,
  stack: Stack,
  weave: WeaveInterface
): Promise<Table.TableState> {
  const rowsNode = Table.getRowsNode(
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    inputNode,
    weave
  );

  const ungroupedCols = tableState.order.filter(
    colId => !tableState.groupBy.includes(colId)
  );
  const groupedColExpressions = tableState.groupBy.map(
    id => tableState.columnSelectFunctions[id]
  );
  const ungroupedColExpressions = ungroupedCols.map(
    id => tableState.columnSelectFunctions[id]
  );

  const groupedCellFrame =
    tableState.groupBy.length > 0
      ? Table.getCellFrame(
          inputNode,
          rowsNode,
          tableState.groupBy,
          tableState.columnSelectFunctions,
          tableState.groupBy[0]
        )
      : {};
  const groupedCellStack = pushFrame(stack, groupedCellFrame);

  const ungroupedCellFrame =
    ungroupedCols.length > 0
      ? Table.getCellFrame(
          inputNode,
          rowsNode,
          tableState.groupBy,
          tableState.columnSelectFunctions,
          ungroupedCols[0]
        )
      : {};
  const ungroupedCellStack = pushFrame(stack, ungroupedCellFrame);

  // TODO: we should do these two calls in parallel!
  const groupedSelectFunctions = await refineExpressions(
    Object.values(groupedColExpressions),
    groupedCellStack,
    weave
  );

  const ungroupedSelectFunctions = await refineExpressions(
    Object.values(ungroupedColExpressions),
    ungroupedCellStack,
    weave
  );

  const newColSelectFunctions: typeof tableState.columnSelectFunctions = {};
  tableState.groupBy.forEach(
    (k, i) => (newColSelectFunctions[k] = groupedSelectFunctions[i])
  );
  ungroupedCols.forEach(
    (k, i) => (newColSelectFunctions[k] = ungroupedSelectFunctions[i])
  );

  return {
    ...tableState,
    columnSelectFunctions: {
      ...tableState.columnSelectFunctions,
      ...newColSelectFunctions,
    },
  };
}

const refineTableStatesExpressions = vectorizePromiseFn(
  refineTableStateExpressions
);
const useTableStateWithRefinedExpressionsUnguarded = makePromiseUsable(
  refineTableStateExpressions
);
const useTableStatesWithRefinedExpressionsUnguarded = makePromiseUsable(
  refineTableStatesExpressions
);

export const useTableStateWithRefinedExpressions: typeof useTableStateWithRefinedExpressionsUnguarded =
  (tableState, inputNode, stack, weave) => {
    const disableRefinement = useWeaveRefinementInReactHooksDisabled();
    // In dashUI, no-op. We manage document refinement in panelTree
    if (disableRefinement) {
      return {
        initialLoading: false,
        loading: false,
        result: tableState,
      };
    }

    // We can ignore this, dashUi is a feature flag that doesn't change during a session
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useTableStateWithRefinedExpressionsUnguarded(
      tableState,
      inputNode,
      stack,
      weave
    );
  };

export const useTableStatesWithRefinedExpressions: typeof useTableStatesWithRefinedExpressionsUnguarded =
  (list, inputNode, stack, weave) => {
    const disableRefinement = useWeaveRefinementInReactHooksDisabled();
    // In dashUI, no-op. We manage document refinement in panelTree
    if (disableRefinement) {
      return {
        initialLoading: false,
        loading: false,
        result: list,
      };
    }

    // We can ignore this, dashUi is a feature flag that doesn't change during a session
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useTableStatesWithRefinedExpressionsUnguarded(
      list,
      inputNode,
      stack,
      weave
    );
  };
