import {
  constNumber,
  dereferenceAllVars,
  isList,
  isListLike,
  isTaggedValue,
  isTypedDict,
  listObjectType,
  ListType,
  MemoizedHasher,
  Node,
  NodeOrVoidNode,
  nonNullableDeep,
  nullableTaggableStrip,
  opIndex,
  opIndexCheckpoint,
  OpStore,
  OutputNode,
  taggedValueValueType,
  Type,
  WeaveInterface,
} from '@wandb/weave/core';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {Stack} from '../../../core';
import {usePanelContext} from '../PanelContext';
import {WeaveFormatContextType} from '../WeaveFormatContext';
import * as Table from './tableState';
import {useTableStateWithRefinedExpressions} from './tableStateReact';

// Formatting for PanelNumbers and PanelStrings inside Tables
export const getColumnCellFormats = (colType: Type): WeaveFormatContextType => {
  const t = nullableTaggableStrip(colType);
  const numberFormat =
    t === 'number'
      ? {
          textAlign: 'right' as const,
          justifyContent: 'normal',
          alignContent: 'normal',
          padding: '4px 8px 0 0',
        }
      : {};
  const stringFormat = {spacing: t === 'string'};
  return {
    numberFormat,
    stringFormat,
  };
};

export const stripTag = (type: Type): Type => {
  return isTaggedValue(type) ? taggedValueValueType(type) : type;
};

// Very simple type shape comparison
export const typeShapesMatch = (type: Type, toType: Type): boolean => {
  type = stripTag(type);
  toType = stripTag(toType);
  if (isList(type) || isList(toType)) {
    if (!isList(type) || !isList(toType)) {
      return false;
    } else {
      return typeShapesMatch(listObjectType(type), listObjectType(toType));
    }
  } else if (isTypedDict(type) || isTypedDict(toType)) {
    if (!isTypedDict(type) || !isTypedDict(toType)) {
      return false;
    } else {
      for (const key of Object.keys(toType.propertyTypes)) {
        const toKeyType = toType.propertyTypes[key]!;
        const keyType = type.propertyTypes[key];
        if (keyType === undefined || !typeShapesMatch(keyType, toKeyType)) {
          return false;
        }
      }
    }
  }
  return true;
};

export const nodeIsValidList = (
  node: NodeOrVoidNode | undefined
): node is Node<ListType<'any'>> => {
  if (node == null || node.nodeType === 'void') {
    return false;
  }
  const nonMaybeType = nonNullableDeep(node.type);
  return isListLike(nonMaybeType) && listObjectType(nonMaybeType) !== 'invalid';
};

export const useAutomatedTableState = (
  input: Node,
  currentTableState: Table.TableState | undefined,
  weave: WeaveInterface
) => {
  const {stack} = usePanelContext();
  // TODO: This was reversing stack and breaking stuff!
  // TODO TODO TODO
  // ({node: input as any, stack} = useRefEqualExpr(input, stack));
  const {table: autoTable} = useMemo(() => {
    const dereffedInput = dereferenceAllVars(input, stack).node as Node;
    return Table.initTableFromTableType(dereffedInput, weave);
  }, [input, stack, weave]);

  const colDiff = Table.tableColumnsDiff(weave, autoTable, currentTableState);
  const isDiff = colDiff.addedCols.length > 0 || colDiff.removedCols.length > 0;
  const tableState =
    currentTableState?.columnNames == null ||
    (currentTableState?.autoColumns === true && isDiff)
      ? autoTable
      : currentTableState;

  const {
    initialLoading,
    loading,
    result: state,
  } = useTableStateWithRefinedExpressions(tableState, input, stack, weave);

  const tableIsDefault = useMemo(() => {
    return (
      currentTableState == null ||
      Table.equalStates(autoTable, currentTableState)
    );
  }, [autoTable, currentTableState]);

  return React.useMemo(
    () => ({
      loading,
      hasLoadedOnce: !initialLoading,
      tableState: state,
      autoTable,
      tableIsDefault,
    }),
    [loading, initialLoading, state, autoTable, tableIsDefault]
  );
};

export const useRowsNode = (
  input: Node,
  tableState: Table.TableState,
  weave: WeaveInterface
) => {
  return useMemo(
    () =>
      Table.getRowsNode(
        tableState.preFilterFunction,
        tableState.groupBy,
        tableState.columnSelectFunctions,
        tableState.columnNames,
        tableState.order,
        tableState.sort,
        opIndexCheckpoint({arr: input}),
        weave
      ),
    [
      tableState.preFilterFunction,
      tableState.groupBy,
      tableState.columnSelectFunctions,
      tableState.columnNames,
      tableState.order,
      tableState.sort,
      input,
      weave,
    ]
  );
};

export const useUpdateConfigKey: <
  T extends {[key: string]: any},
  K extends keyof T
>(
  key: K,
  updateConfig: (partialConfig: Partial<T>) => void
) => (val: T[K] | undefined) => void = (key, updateConfig) => {
  return useCallback(
    val => {
      // Arg: i couldn't get rid of need for this 'as any'
      updateConfig({
        [key]: val,
      } as any);
    },
    [updateConfig, key]
  );
};

export const useBaseTableColumnDefinitions = (
  orderedColumns: string[],
  tableState: Table.TableState,
  opStore: OpStore
) => {
  return useMemo(() => {
    const hasher = new MemoizedHasher();
    return _.fromPairs(
      _.map(orderedColumns, colId => {
        const columnDefinition = {
          id: colId,
          name: Table.getTableColumnName(
            tableState.columnNames,
            tableState.columnSelectFunctions,
            colId,
            opStore
          ),
          selectFn: tableState.columnSelectFunctions[colId],
          isGrouped: tableState.groupBy.includes(colId),
          sortDirection: tableState.sort.find(s => s.columnId === colId)?.dir,
          panelId: tableState.columns[colId].panelId,
          panelConfig: tableState.columns[colId].panelConfig,
          key: '',
        };
        let columnKey = '';
        columnKey += `${columnDefinition.id}`;
        columnKey += `-${columnDefinition.name}`;
        columnKey += `-${
          columnDefinition.selectFn.nodeType === 'void'
            ? 'v'
            : hasher.typedNodeId(columnDefinition.selectFn)
        }`;
        columnKey += `-${columnDefinition.isGrouped}`;
        columnKey += `-${columnDefinition.sortDirection ?? '_'}`;
        columnKey += `-${columnDefinition.panelId}`;
        columnDefinition.key = columnKey;
        return [colId, columnDefinition];
      })
    );
  }, [
    orderedColumns,
    tableState.columnNames,
    tableState.columnSelectFunctions,
    tableState.groupBy,
    tableState.sort,
    tableState.columns,
    opStore,
  ]);
};

export const useOrderedColumns = (
  tableState: Table.TableState,
  pinnedColumns: string[],
  countColumnId: string | null
) => {
  return useMemo(() => {
    const allColumns = Table.getColumnRenderOrder(tableState);
    let countColumn = countColumnId ?? '';
    let groupCountColumn = [countColumn];
    if (!allColumns.includes(countColumn)) {
      countColumn = '';
      groupCountColumn = [];
    }
    const normalColumns = allColumns
      .filter(s => !pinnedColumns.includes(s))
      .filter(s => s !== countColumn);
    const actualPinnedColumns = allColumns
      .filter(s => pinnedColumns.includes(s))
      .filter(s => s !== countColumn);

    return tableState.groupBy
      .concat(groupCountColumn)
      .concat(actualPinnedColumns)
      .concat(normalColumns);
  }, [tableState, pinnedColumns, countColumnId]);
};

export const getTableMeasurements = (args: {
  height: number;
  width: number;
  orderedColumns: string[];
  columnWidths: {[key: string]: number};
  rowHeight: number;
  numberOfHeaders: number;
  headerHeight: number;
  footerHeight: number;
  totalRowCount: number | undefined;
  indexOffset: number;
  baseColumnWidth: number;
  rowControlsWidth: number;
  numPinnedRows: number;
}) => {
  const {
    height,
    width,
    orderedColumns,
    columnWidths,
    rowHeight,
    numberOfHeaders,
    headerHeight,
    footerHeight,
    totalRowCount,
    indexOffset,
    baseColumnWidth,
    rowControlsWidth,
    numPinnedRows,
  } = args;
  const hasHorizontalScroll =
    width <
    _.sum(
      orderedColumns.map(c => {
        return columnWidths[c] ?? baseColumnWidth;
      })
    ) +
      rowControlsWidth;
  const scrollAllocation = 14;
  const contentSpace =
    height -
    numberOfHeaders * headerHeight -
    footerHeight -
    (hasHorizontalScroll ? scrollAllocation : 0);
  const unboundedRowsPerPage = Math.max(
    1,
    Math.floor(contentSpace / rowHeight)
  );
  const rowsPerPage =
    totalRowCount == null
      ? unboundedRowsPerPage
      : Math.min(unboundedRowsPerPage, totalRowCount + numPinnedRows);
  const adaptiveRowHeight = Math.floor(contentSpace / Math.max(rowsPerPage, 1));

  const minIndexOffset = 0;
  const maxIndexOffset =
    totalRowCount == null
      ? 10000000
      : Math.min(totalRowCount - rowsPerPage + numPinnedRows);

  const adjustedIndexOffset = Math.max(
    minIndexOffset,
    Math.min(indexOffset, maxIndexOffset)
  );
  const numVisibleRows = rowsPerPage - numPinnedRows;
  // totalRowCount == null
  //   ? 0
  //   : Math.min(rowsPerPage, totalRowCount - adjustedIndexOffset) -
  //     numPinnedRows;
  return {
    adaptiveRowHeight,
    adjustedIndexOffset,
    numVisibleRows,
    rowsPerPage,
  };
};

export type BaseTableDataType = {
  id: string;
  rowNode: OutputNode<Type>;
  isPinned: boolean;
};
export const useBaseTableData = (
  rowsNode: Node,
  unfilteredRowsNode: Node,
  rowsPerPage: number,
  adjustedIndexOffset: number,
  pinnedRows: number[],
  unfilteredTotalRowCount: number | undefined
): {
  unpinnedData: BaseTableDataType[];
  pinnedData: BaseTableDataType[];
} => {
  pinnedRows = useMemo(
    () =>
      unfilteredTotalRowCount != null
        ? pinnedRows.filter(ndx => ndx < unfilteredTotalRowCount)
        : [],
    [pinnedRows, unfilteredTotalRowCount]
  );
  const adjustedPinnedRows = useMemo(
    () =>
      pinnedRows.slice(
        0,
        Math.min(Math.max(0, rowsPerPage - 1), pinnedRows.length)
      ),
    [pinnedRows, rowsPerPage]
  );

  const numUnpinnedRows = rowsPerPage - adjustedPinnedRows.length;

  const unpinnedData = useMemo(() => {
    const hasher = new MemoizedHasher();
    return _.range(numUnpinnedRows).map(val => {
      const rowNode = opIndex({
        arr: rowsNode,
        index: constNumber(adjustedIndexOffset + val),
      });
      return {
        id: hasher.typedNodeId(rowNode),
        rowNode,
        isPinned: false,
      };
    });
  }, [rowsNode, numUnpinnedRows, adjustedIndexOffset]);

  const pinnedData = useMemo(() => {
    const hasher = new MemoizedHasher();
    return adjustedPinnedRows.map(val => {
      const rowNode = opIndex({
        arr: unfilteredRowsNode,
        index: constNumber(val),
      });
      return {
        id: hasher.typedNodeId(rowNode),
        rowNode,
        isPinned: true,
      };
    });
  }, [unfilteredRowsNode, adjustedPinnedRows]);

  return {unpinnedData, pinnedData};
};

// This is used to determine if a PanelTable is a ChildPanel
// We do not want to render row selection styles if the activeData of the PanelTable cannot be used
// If PanelTable is a ChildPanel, there will exist a variable in the stack that is an input
export const tableIsPanelVariable = (stack: Stack) => {
  return stack && stack.find(node => node.name === 'input') !== undefined;
};
