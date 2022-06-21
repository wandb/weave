import * as Types from '@wandb/cg/browser/model/types';
import * as Op from '@wandb/cg/browser/ops';
import {MemoizedHasher} from '@wandb/cg/browser/hash';
import _ from 'lodash';
import {useCallback, useMemo} from 'react';
import * as Table from './tableState';
import {useTableStateWithRefinedExpressions} from './tableStateReact';

const stripTag = (type: Types.Type): Types.Type => {
  return Types.isTaggedValue(type) ? Types.taggedValueValueType(type) : type;
};

// Very simple type shape comparison
export const typeShapesMatch = (
  type: Types.Type,
  toType: Types.Type
): boolean => {
  type = stripTag(type);
  toType = stripTag(toType);
  if (Types.isList(type) || Types.isList(toType)) {
    if (!Types.isList(type) || !Types.isList(toType)) {
      return false;
    } else {
      return typeShapesMatch(
        Types.listObjectType(type),
        Types.listObjectType(toType)
      );
    }
  } else if (Types.isTypedDict(type) || Types.isTypedDict(toType)) {
    if (!Types.isTypedDict(type) || !Types.isTypedDict(toType)) {
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
  node: Types.NodeOrVoidNode | undefined
): node is Types.Node<Types.ListType<'any'>> => {
  return (
    node != null &&
    node.nodeType !== 'void' &&
    Types.isListLike(node.type) &&
    Types.listObjectType(node.type) !== 'invalid'
  );
};

export const useAutomatedTableState = (
  input: Types.Node,
  currentTableState: Table.TableState | undefined
) => {
  const {table: autoTable, allColumns} = useMemo(
    () => Table.initTableFromTableType(input),
    [input]
  );

  const colDiff = Table.tableColumnsDiff(autoTable, currentTableState);
  const isDiff = colDiff.addedCols.length > 0 || colDiff.removedCols.length > 0;
  const tableState =
    currentTableState?.columnNames == null ||
    (currentTableState?.autoColumns === true && isDiff)
      ? autoTable
      : currentTableState;

  const {tableState: state} = useTableStateWithRefinedExpressions(
    input,
    tableState
  );

  const tableIsDefault = useMemo(() => {
    return (
      currentTableState == null ||
      Table.equalStates(autoTable, currentTableState)
    );
  }, [autoTable, currentTableState]);

  return {tableState: state, autoTable, tableIsDefault, allColumns};
};

export const useRowsNode = (
  input: Types.Node,
  tableState: Table.TableState
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
        Op.opIndexCheckpoint({arr: input})
      ),
    [
      tableState.preFilterFunction,
      tableState.groupBy,
      tableState.columnSelectFunctions,
      tableState.columnNames,
      tableState.order,
      tableState.sort,
      input,
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
  tableState: Table.TableState
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
            colId
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
  ]);
};

export const useOrderedColumns = (
  tableState: Table.TableState,
  pinnedColumns: string[]
) => {
  return useMemo(() => {
    const allColumns = Table.getColumnRenderOrder(tableState);
    const normalColumns = allColumns.filter(s => !pinnedColumns.includes(s));
    const actualPinnedColumns = allColumns.filter(s =>
      pinnedColumns.includes(s)
    );

    return tableState.groupBy.concat(actualPinnedColumns).concat(normalColumns);
  }, [tableState, pinnedColumns]);
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
  rowNode: Types.OutputNode<Types.Type>;
  isPinned: boolean;
};
export const useBaseTableData = (
  rowsNode: Types.Node,
  unfilteredRowsNode: Types.Node,
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
      const rowNode = Op.opIndex({
        arr: rowsNode,
        index: Op.constNumber(adjustedIndexOffset + val),
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
      const rowNode = Op.opIndex({
        arr: unfilteredRowsNode,
        index: Op.constNumber(val),
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
