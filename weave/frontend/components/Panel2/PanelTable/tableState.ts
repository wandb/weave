import _ from 'lodash';
import produce from 'immer';

import * as ID from '@wandb/cg/browser/utils/id';
import * as HL from '@wandb/cg/browser/hl';
import * as Code from '@wandb/cg/browser/code';
import * as Graph from '@wandb/cg/browser/graph';
import * as Op from '@wandb/cg/browser/ops';
import * as Types from '@wandb/cg/browser/model/types';
import * as TypeHelpers from '@wandb/cg/browser/model/typeHelpers';
import {escapeDots} from '@wandb/cg/browser/ops';
import {Client} from '@wandb/cg/browser';

export type ColumnId = string;

interface TableColumnPanel {
  panelId: string;
  panelConfig: any;

  // For columns that are simple property keys
  // Need this to construct the set: {hiddenKeys} = {allKeys} - {visibleKeys}
  originalKey?: any;
}

interface Sort {
  dir: 'asc' | 'desc';
  columnId: string;
}

type ColumnSelectFunctions = {
  [id: string]: Types.NodeOrVoidNode;
};

type ColumnOrder = ColumnId[];
type GroupByColumns = ColumnId[];

export interface TableState {
  autoColumns: boolean;
  columns: {
    [id: string]: TableColumnPanel;
  };

  preFilterFunction: Types.NodeOrVoidNode;

  // A table's rows node depends on the filters,
  // which depend on the column filter and select functions.
  // Store them seperately from the table column panel config,
  // so we don't recompute the row node if the panel config
  // changes
  columnNames: {[id: string]: string};
  columnSelectFunctions: ColumnSelectFunctions;
  order: ColumnOrder;
  groupBy: GroupByColumns;
  sort: Sort[];
  pageSize: number;
  page: number;
}

function newColumnId() {
  return 'col-' + ID.ID();
}

export function emptyTable(): TableState {
  return {
    autoColumns: true,
    columns: {},
    columnNames: {},
    preFilterFunction: Graph.voidNode(),
    columnSelectFunctions: {},
    order: [],
    groupBy: [],
    sort: [],
    pageSize: 10,
    page: 0,
  };
}

export function defaultTable(inputArrayNode: Types.Node): TableState {
  const exampleRow = getExampleRow(inputArrayNode);
  const availOps = HL.availableOpsForChain(exampleRow.type);
  let tableState = emptyTable();
  const nameOpDef = availOps.find(op => op.name.endsWith('-name'));
  if (nameOpDef != null) {
    tableState = appendEmptyColumn(tableState);
    const colId = tableState.order[tableState.order.length - 1];
    const argName0 = Object.keys(nameOpDef.inputTypes)[0];
    const called = HL.callOpValid(nameOpDef.name, {
      [argName0]: Graph.varNode(exampleRow.type, 'row'),
    });
    tableState = updateColumnSelect(tableState, colId, called);
  }
  return tableState;
}

export function initTableWithPickColumns(
  pickCols: string[],
  inputArrayNode: Types.Node
) {
  let ts = emptyTable();
  const exNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode
  );
  if (pickCols.length === 0) {
    // If no columns are provided, at least fill it with a general row column.
    ts = addColumnToTable(ts, Graph.varNode(exNode.type, 'row')).table;
  } else {
    const addCols: AddColumnEntries = pickCols.map(colKey => ({
      selectFn: Op.opPick({
        obj: Graph.varNode(exNode.type, 'row') as any,
        key: Op.constString(colKey),
      }),
      keyName: colKey,
    }));

    ts = addColumnsToTable(ts, addCols).table;
  }
  return ts;
}

function isNDArrayLike(type: Types.Type): boolean {
  type = Types.nullableTaggableValue(type);
  if (Types.isSimpleType(type)) {
    return false;
  } else if (type.type === 'ndarray') {
    return true;
  } else if (Types.isListLike(type)) {
    return isNDArrayLike(Types.listObjectType(type));
  }
  return false;
}

// Try to pick nice default columns to make a table for the given object
// type. See the initial columns test in tableState.test.ts to see examples
// of current behavior.
export function initTableColumnsFromObjectType(
  objectType: Types.Type
): string[] {
  const allPaths = TypeHelpers.allObjPaths(objectType).filter(
    path => !isNDArrayLike(path.type)
  );
  return allPaths.map(pt => pt.path.map(escapeDots).join('.'));
}

// Given a row node that we're going to render as a table, try to
// pick a good set of default columns.
// This doesn't really have enough information to do a great job.
// We may want to call it from WBJoinedTable and WBTable instead
// of PanelTable, where we no longer have a table and just have an
// array of objects. Or we could walk up the graph from here to
// determine where our array came from...
export function initTableFromTableType(inputArrayNode: Types.Node) {
  const arrayType = inputArrayNode.type;
  let allColumns: string[] = [];
  const objectType = Types.listObjectType(arrayType);
  if (
    Types.isAssignableTo2(Types.nonNullable(objectType), Types.typedDict({}))
  ) {
    allColumns = initTableColumnsFromObjectType(objectType);
  }
  const columns =
    allColumns.length > 100 ? allColumns.slice(0, 100) : allColumns;

  let table = initTableWithPickColumns(columns, inputArrayNode);
  table = maybeAddCompareColumn(table, inputArrayNode);
  table = setAutoColumns(table, true);
  return {table, allColumns};
}

function maybeAddCompareColumn(table: TableState, inputNode: Types.Node) {
  if (inputNode.nodeType === 'output' && inputNode.fromOp.name === 'joinAll') {
    const joinObjNode = Op.opGetJoinedJoinObj({
      obj: Graph.varNode(getExampleRow(inputNode).type, 'row'),
    });
    if (joinObjNode.type !== 'invalid' && joinObjNode.type !== 'none') {
      table = prependColumn(table, inputNode);
      table = updateColumnSelect(table, table.order[0], joinObjNode);
      table = updateColumnName(table, table.order[0], 'Joined On');
      table = setAutoColumns(table, true);
    }

    let joinedOnKeys: string[] = [];
    if (
      inputNode.fromOp.inputs.joinFn.nodeType === 'const' &&
      Types.isFunction(inputNode.fromOp.inputs.joinFn.type)
    ) {
      const fnOp = inputNode.fromOp.inputs.joinFn.val.fromOp as Types.Op;
      if (fnOp.name === 'pick') {
        const keyNode = fnOp.inputs.key;
        if (keyNode.nodeType === 'const') {
          joinedOnKeys = [keyNode.val];
        }
      } else if (fnOp.name === 'none-coalesce') {
        let coalesceOp: Types.Op | null = fnOp;
        while (coalesceOp != null) {
          const rhsNode = coalesceOp.inputs.rhs;
          if (rhsNode.nodeType === 'output' && rhsNode.fromOp.name === 'pick') {
            const rhsNodeKeyNode = rhsNode.fromOp.inputs.key;
            if (rhsNodeKeyNode.nodeType === 'const') {
              joinedOnKeys.push(rhsNodeKeyNode.val);
            }
          }
          const lhsNode: Types.Node = coalesceOp.inputs.lhs;
          coalesceOp = null;
          if (lhsNode.nodeType === 'output' && lhsNode.fromOp.name === 'pick') {
            const lhsNodeKeyNode = lhsNode.fromOp.inputs.key;
            if (lhsNodeKeyNode.nodeType === 'const') {
              joinedOnKeys.push(lhsNodeKeyNode.val);
            }
          } else if (
            lhsNode.nodeType === 'output' &&
            lhsNode.fromOp.name === 'none-coalesce'
          ) {
            coalesceOp = lhsNode.fromOp;
          }
        }
      }
    }

    joinedOnKeys = joinedOnKeys.flatMap(joinedOnKey => {
      const parts = joinedOnKey.split('.');
      parts.splice(1, 0, '*');
      return [joinedOnKey, parts.join('.')];
    });

    _.keys(table.columnSelectFunctions)
      .filter(key => {
        const selectFn = table.columnSelectFunctions[key];
        if (
          selectFn.nodeType === 'output' &&
          selectFn.fromOp.inputs.key?.nodeType === 'const'
        ) {
          return joinedOnKeys.includes(
            (selectFn.fromOp.inputs.key as Types.ConstNode).val as string
          );
        }
        return false;
      })
      .forEach(colId => {
        table = removeColumn(table, colId);
      });
    table = setAutoColumns(table, true);
  }
  return table;
}

export function tableColumnsDiff(toTable: TableState, fromTable?: TableState) {
  const toTableCols = new Set<string>();
  const fromTableCols = new Set<string>();

  for (const colSelFn of Object.values(toTable.columnSelectFunctions)) {
    toTableCols.add(HL.toString(colSelFn));
  }
  if (fromTable != null && fromTable.columnNames != null) {
    for (const colSelFn of Object.values(fromTable.columnSelectFunctions)) {
      fromTableCols.add(HL.toString(colSelFn));
    }
  }
  const addedCols: string[] = [];
  for (const [key] of toTableCols.entries()) {
    if (!fromTableCols.has(key)) {
      addedCols.push(key);
    }
  }
  const removedCols: string[] = [];
  for (const [key] of fromTableCols.entries()) {
    if (!toTableCols.has(key)) {
      removedCols.push(key);
    }
  }
  return {addedCols, removedCols};
}

function cleanObj(obj: any) {
  const newObj: {[key: string]: any} = {};
  for (const propName in obj) {
    if (obj[propName] !== undefined) {
      newObj[propName] = obj[propName];
    }
  }
  return newObj;
}

export function equalStates(aTable: TableState, bTable?: TableState) {
  if (!bTable) {
    return false;
  } else if (aTable.order?.length !== bTable.order?.length) {
    return false;
  } else if (
    !_.isEqual(
      aTable.sort.map(s => aTable.order.indexOf(s.columnId)),
      bTable.sort.map(s => bTable.order.indexOf(s.columnId))
    ) ||
    !_.isEqual(
      aTable.sort.map(s => s.dir),
      bTable.sort.map(s => s.dir)
    )
  ) {
    return false;
  } else if (
    !_.isEqual(
      aTable.groupBy.map(s => aTable.order.indexOf(s)),
      bTable.groupBy.map(s => bTable.order.indexOf(s))
    )
  ) {
    return false;
  } else if (!_.isEqual(aTable.preFilterFunction, bTable.preFilterFunction)) {
    return false;
  } else {
    for (let i = 0; i < aTable.order.length; i++) {
      const aID = aTable.order[i];
      const bID = bTable.order[i];
      if (
        aTable.columnNames[aID] !== bTable.columnNames[bID] ||
        !_.isEqual(
          aTable.columnSelectFunctions[aID],
          bTable.columnSelectFunctions[bID]
        ) ||
        !_.isEqual(cleanObj(aTable.columns[aID]), cleanObj(bTable.columns[bID]))
      ) {
        return false;
      }
    }
  }
  return true;
}

export function appendEmptyColumn(ts: TableState) {
  const colId = newColumnId();
  return produce(ts, draft => {
    draft.columns[colId] = {
      panelId: '',
      panelConfig: undefined,
    };
    draft.columnNames[colId] = '';
    draft.columnSelectFunctions[colId] = Graph.voidNode();
    draft.order.push(colId);
  });
}

export function appendColumn(ts: TableState, inputNode: Types.Node) {
  const colId = newColumnId();
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputNode
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[colId] = {
      panelId: '',
      panelConfig: undefined,
    };
    draft.columnNames[colId] = '';
    draft.columnSelectFunctions[colId] = Graph.varNode(
      rowExampleNode.type,
      'row'
    );
    draft.order.push(colId);
  });
}

export function prependColumn(ts: TableState, inputNode: Types.Node) {
  const colId = newColumnId();
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputNode
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[colId] = {
      panelId: '',
      panelConfig: undefined,
    };
    draft.columnNames[colId] = '';
    draft.columnSelectFunctions[colId] = Graph.varNode(
      rowExampleNode.type,
      'row'
    );
    draft.order.unshift(colId);
  });
}

export function setAutoColumns(ts: TableState, autoColumns: boolean) {
  return produce(ts, draft => {
    draft.autoColumns = autoColumns;
  });
}

export function updatePreFilter(
  ts: TableState,
  filterFn: Types.NodeOrVoidNode
) {
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.preFilterFunction = filterFn;
  });
}

export function updateColumnName(ts: TableState, colId: string, name: string) {
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columnNames[colId] = name;
  });
}

export function updateColumnSelect(
  ts: TableState,
  colId: string,
  selectFn: Types.NodeOrVoidNode
) {
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columnSelectFunctions[colId] = selectFn;
  });
}

export function updateColumnPanelId(
  ts: TableState,
  colId: string,
  panelId: string
) {
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[colId].panelId = panelId;
  });
}

export function updateColumnPanelConfig(
  ts: TableState,
  colId: string,
  config: any
) {
  return produce(ts, draft => {
    // Annoyingly, we can't disable auto-columns here. It results in an
    // infinite loops because of PanelImage, which updates its config in
    // its render function, causing an infinite loop.
    // TODO: fix this once we fix PanelImage.
    // draft.autoColumns = false;
    if (draft.columns[colId].panelConfig == null) {
      draft.columns[colId].panelConfig = {};
    }
    Object.assign(draft.columns[colId].panelConfig, config);
  });
}

export function setPage(ts: TableState, page: number) {
  return produce(ts, draft => {
    draft.page = page;
  });
}

export async function enableGroupByCol(
  client: Client,
  ts: TableState,
  colId: string | string[],
  inputArrayNode: Types.Node,
  frame: Code.Frame
) {
  const colIds = _.isArray(colId) ? colId : [colId];
  ts = produce(ts, draft => {
    draft.autoColumns = false;
    for (const cid of colIds) {
      if (ts.columns[cid] == null) {
        throw new Error('invalid group by col id' + cid);
      }
      if (ts.groupBy.includes(cid)) {
        return;
      }
      draft.groupBy.push(cid);
    }
  });
  ts = await refreshSelectFunctions(ts, inputArrayNode, client, frame);
  return ts;
}

export async function disableGroupByCol(
  client: Client,
  ts: TableState,
  colId: string | string[],
  inputArrayNode: Types.Node,
  frame: Code.Frame
) {
  const colIds = _.isArray(colId) ? colId : [colId];
  const groupBy = ts.groupBy;
  ts = produce(ts, draft => {
    draft.autoColumns = false;
    for (const cid of colIds) {
      if (ts.columns[cid] == null) {
        throw new Error('invalid group by col id' + cid);
      }
      if (!groupBy.includes(cid)) {
        return;
      }
      const orderIndex = draft.groupBy.indexOf(cid);
      draft.groupBy.splice(orderIndex, 1);
    }
  });
  ts = await refreshSelectFunctions(ts, inputArrayNode, client, frame);
  return ts;
}

export function enableSortByCol(ts: TableState, colId: string, asc: boolean) {
  const dir = asc ? 'asc' : 'desc';
  if (ts.columns[colId] == null) {
    throw new Error('invalid sort by col id' + colId);
  }
  let matchedIndex: number | null = null;
  for (let i = 0; i < ts.sort.length; i++) {
    if (ts.sort[i].columnId === colId) {
      matchedIndex = i;
      if (ts.sort[i].dir === dir) {
        return ts;
      } else {
        break;
      }
    }
  }
  ts = produce(ts, draft => {
    draft.autoColumns = false;
    const newSort: Sort = {
      dir,
      columnId: colId,
    };
    if (matchedIndex == null) {
      draft.sort.push(newSort);
    } else {
      draft.sort[matchedIndex] = newSort;
    }
  });
  return ts;
}

export function disableSortByCol(ts: TableState, colId: string) {
  ts = produce(ts, draft => {
    draft.autoColumns = false;
    draft.sort = draft.sort.filter(s => s.columnId !== colId);
  });
  return ts;
}

export function disableSort(ts: TableState) {
  ts = produce(ts, draft => {
    draft.sort = [];
  });
  return ts;
}

export function insertColumnRight(
  ts: TableState,
  colId: string,
  inputArrayNode: Types.Node
) {
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid insert col id' + colId);
  }

  const newColId = newColumnId();
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[newColId] = {
      panelId: '',
      panelConfig: {},
    };
    draft.columnNames[newColId] = '';
    draft.columnSelectFunctions[newColId] = Graph.varNode(
      rowExampleNode.type,
      'row'
    );
    draft.order.splice(colIndex + 1, 0, newColId);
  });
}

export function insertColumnLeft(
  ts: TableState,
  colId: string,
  inputArrayNode: Types.Node
) {
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid insert col id' + colId);
  }

  const newColId = newColumnId();
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[newColId] = {
      panelId: '',
      panelConfig: {},
    };
    draft.columnNames[newColId] = '';
    draft.columnSelectFunctions[newColId] = Graph.varNode(
      rowExampleNode.type,
      'row'
    );
    draft.order.splice(colIndex, 0, newColId);
  });
}

export function removeColumn(ts: TableState, colId: string) {
  if (ts.groupBy.includes(colId)) {
    // We don't allow removing the group by column. The UI
    // doesn't expose this as an option. This check prevents
    // removeColumnsToLeft and removeColumnsToRight from
    // removing the group by columns and causing an invalid
    // state.
    return ts;
  }
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid remove col id' + colId);
  }
  return produce(ts, draft => {
    draft.autoColumns = false;
    delete draft.columns[colId];
    delete draft.columnNames[colId];
    delete draft.columnSelectFunctions[colId];
    draft.sort = draft.sort.filter(sort => sort.columnId !== colId);
    draft.order.splice(colIndex, 1);
  });
}

export function removeColumnsToRight(ts: TableState, colId: string) {
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid remove col id' + colId);
  }
  for (let i = ts.order.length - 1; i > colIndex; i--) {
    ts = removeColumn(ts, ts.order[i]);
  }
  return ts;
}

export function removeColumnsToLeft(ts: TableState, colId: string) {
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid remove col id' + colId);
  }
  for (let i = colIndex - 1; i > 0; i--) {
    ts = removeColumn(ts, ts.order[i]);
  }
  return ts;
}

// Get what a column's expression would be if there were no grouping set.
export async function getUngroupedSelectFunction(
  client: Client,
  inputArrayNode: Types.Node,
  frame: Code.Frame,
  colSelectFn: Types.NodeOrVoidNode
) {
  if (colSelectFn.nodeType === 'void') {
    return Promise.resolve(Graph.voidNode());
  }
  const cellFrame = {
    ...frame,
    row: getExampleRow(inputArrayNode),
  };
  return HL.updateFunctionForInputs(
    client,
    colSelectFn,
    cellFrame
  ) as Promise<Types.NodeOrVoidNode>;
}

export async function refreshSelectFunctions(
  ts: TableState,
  inputArrayNode: Types.Node,
  client: Client,
  frame: Code.Frame
) {
  const rowsNode = getRowsNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode
  );
  const cols = ts.order;
  const newSelectFns = await Promise.all(
    cols.map(colId => {
      const cellFrame = getCellFrame(
        inputArrayNode,
        rowsNode,
        frame,
        ts.groupBy,
        ts.columnSelectFunctions,
        colId
      );
      const colSelectFn = ts.columnSelectFunctions[colId];
      if (colSelectFn.nodeType === 'void') {
        return Promise.resolve(Graph.voidNode());
      }
      return HL.updateFunctionForInputs(
        client,
        colSelectFn,
        cellFrame
      ) as Promise<Types.NodeOrVoidNode>;
    })
  );
  cols.forEach(
    (colId, i) => (ts = updateColumnSelect(ts, colId, newSelectFns[i]))
  );
  return ts;
}

function getUnaggedAncestor(selectFn: Types.Node<Types.Type>) {
  return HL.findChainedAncestor(
    selectFn,
    n => {
      return (
        n.nodeType === 'output' &&
        Types.nDims(n.type) >=
          Types.nDims(Object.values(n.fromOp.inputs)[0].type)
      );
    },
    n => true
  );
}

function getDimExpandingAncestor(selectFn: Types.Node<Types.Type>) {
  return HL.findChainedAncestor(
    selectFn,
    n => {
      return (
        n.nodeType === 'output' &&
        Types.nDims(n.type) >
          Types.nDims(Object.values(n.fromOp.inputs)[0].type)
      );
    },
    n => true
  );
}

export function getRowFrame(inputNode: Types.Node, frame: Code.Frame) {
  return {
    ...frame,
    row: getExampleRow(inputNode),
    // Don't include index in frame for now. We don't need it yet.
    // index: CG.varNode('number', 'index'),
    // Don't include arr in frame for now. We don't need it yet and
    // need to fix suggest ordering before including it.
    // arr: inputNode,
  };
}

export function getCellFrame(
  inputNode: Types.Node,
  rowsNode: Types.Node,
  frame: Code.Frame,
  groupByColumns: ColumnId[],
  columnSelectFunctions: ColumnSelectFunctions,
  colId: string
) {
  // In the normal case, we select from an example row from input.
  let exampleNode: Types.Node;
  if (needsUnnestQuery(groupByColumns, columnSelectFunctions)) {
    const selectFn = columnSelectFunctions[colId];
    if (
      selectFn.nodeType !== 'void' &&
      getDimExpandingAncestor(selectFn) != null
    ) {
      exampleNode = getExampleRow(inputNode);
    } else {
      exampleNode = inputNode;
    }
  } else {
    if (
      isGrouped(groupByColumns, columnSelectFunctions) &&
      !groupByColumns.includes(colId)
    ) {
      exampleNode = getExampleRow(rowsNode);
    } else {
      exampleNode = getExampleRow(inputNode);
    }
  }
  const newFrame: Code.Frame = Types.isList(inputNode.type)
    ? {
        ...frame,
        row: exampleNode,
        // index: Graph.varNode('number', 'index'),
        // Don't include arr in frame for now. We don't need it yet and
        // need to fix suggest ordering before including it.
        // arr: inputNode,
      }
    : {
        ...frame,
        row: exampleNode,
        // key: Graph.varNode('string', 'key'),
      };
  return newFrame;
}

function isGrouped(
  groupByColumns: ColumnId[],
  columnSelectFunctions: ColumnSelectFunctions
) {
  for (const colId of groupByColumns) {
    const selectFn = columnSelectFunctions[colId];
    if (selectFn.type !== 'invalid') {
      return true;
    }
  }
  return false;
}

function needsUnnestQuery(
  groupByColumns: ColumnId[],
  columnSelectFunctions: ColumnSelectFunctions
) {
  // Disabled for now because of a logic bug: we need to call this
  // to get the rowsNode, which we need to do refreshSelectFunctions.

  // But if we've grouped by column c, column a will be a[]. If we're now
  // trying to enable grouping for column a, we get the wrong answer since
  // its an array. We need to know what its type would be without grouping.
  // TODO: Fix when enabling automatic unnest.
  return false;
  // for (const colId of groupByColumns) {
  //   const selectFn = columnSelectFunctions[colId];
  //   if (
  //     selectFn.nodeType !== 'void' &&
  //     selectFn.type !== 'invalid' &&
  //     Types.isAssignableTo2(selectFn.type, Types.list('any'))
  //   ) {
  //     console.log(
  //       'RETURNING NEEDS UNNEST TRUE',
  //       selectFn.type,
  //       HL.toString(selectFn)
  //     );
  //     return true;
  //   }
  // }
  // return false;
}

export function getColumnRenderOrder(tableState: TableState) {
  return tableState.order.filter(colId => !tableState.groupBy.includes(colId));
}

export function getExampleRow(exampleRowsNode: Types.Node) {
  return Op.opIndex({
    arr: exampleRowsNode as any,
    index: Graph.varNode('number', 'n'),
  });
}

function getRowExampleNode(
  preFilterFunction: Types.NodeOrVoidNode,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  order: ColumnOrder,
  sortByColumns: Sort[],
  inputArrayNode: Types.Node
) {
  const visibleRowsNode = getRowsNode(
    preFilterFunction,
    groupByColumns,
    columnSelectFunctions,
    columnNames,
    order,
    sortByColumns,
    inputArrayNode
  );
  if (groupByColumns.length > 0) {
    return getExampleRow(visibleRowsNode);
  } else {
    return getExampleRow(inputArrayNode);
  }
}

function getComparableDataFn(
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[id: string]: string},
  groupBy: GroupByColumns,
  sortBy: Sort[],
  inputNode: Types.Node
) {
  const exampleRowNode = Op.opIndex({
    arr: inputNode as any,
    index: Graph.varNode('number', 'n'),
  });

  if (sortBy.length === 0) {
    throw new Error('Invalid sortBy value');
  }

  const colVals: {[key: string]: Types.Node} = {};
  for (const sort of sortBy) {
    const colSelectFunction = columnSelectFunctions[sort.columnId];
    let colVal: Types.Node = Graph.varNode(exampleRowNode.type, 'row');
    if (colSelectFunction.nodeType !== 'void') {
      if (groupBy.includes(sort.columnId)) {
        colVal = Op.opPick({
          obj: Op.opGroupGroupKey({obj: colVal}),
          key: Op.constString(
            getTableColumnName(
              columnNames,
              columnSelectFunctions,
              sort.columnId
            )
          ),
        });
      } else {
        colVal = HL.callFunction(colSelectFunction, {
          row: colVal as any,
        });
      }
    }
    colVals[sort.columnId] = colVal;
  }
  if (Object.keys(colVals).length === 0) {
    return Graph.voidNode();
  }
  return Op.opArray(colVals as any);
}

export function getPagedRowsNode(
  pageSize: number,
  page: number,
  rowsNode: Types.Node
) {
  let node = Op.opOffset({
    arr: rowsNode as any,
    offset: Op.constNumber(pageSize * page),
  });
  node = Op.opLimit({
    arr: node as any,
    limit: Op.constNumber(pageSize),
  });
  return node;
}

function groupDict(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string}
) {
  const groupedNode: {[key: string]: Types.Node} = {};
  for (const colId of order) {
    if (groupByColumns.includes(colId)) {
      const selectFn = columnSelectFunctions[colId];
      if (selectFn.type !== 'invalid') {
        const colName = getTableColumnName(
          columnNames,
          columnSelectFunctions,
          colId
        );
        groupedNode[colName] = selectFn;
      }
    }
  }
  return groupedNode;
}

function groupByNodeForUnnestStyle(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  node: Types.Node<Types.Type>
) {
  const groupedNode = groupDict(
    order,
    groupByColumns,
    columnSelectFunctions,
    columnNames
  );
  const allNode = {...groupedNode};
  for (const colId of order) {
    // For all not group columns, split the node at the point where
    // aggregation starts, we select the pre-aggregation part here.
    if (!groupByColumns.includes(colId)) {
      const selectFn = columnSelectFunctions[colId];
      if (selectFn.nodeType !== 'void') {
        const unagged = getUnaggedAncestor(selectFn);
        const colName = getTableColumnName(
          columnNames,
          columnSelectFunctions,
          colId
        );
        if (unagged != null) {
          allNode[colName] = unagged;
          const dimExpand = getDimExpandingAncestor(selectFn);
          if (dimExpand == null) {
            // Insane type hacking,
            let type = unagged.type;
            if (Types.isTaggedValue(type)) {
              type = type.value;
            }
            if (Types.isList(type)) {
              allNode[colName] = {
                ...allNode[colName],
                type: type.objectType,
              };
            }
          }
        }
      }
    }
  }

  // first unnest all array columns
  node = Op.opMap({
    arr: node as any,
    mapFn: Op.defineFunction({row: getExampleRow(node).type}, ({row}) =>
      Op.opDict(allNode as any)
    ),
  });
  node = Op.opUnnest({
    arr: node as any,
  });
  const unnestedType = node.type;
  if (!Types.isList(unnestedType)) {
    throw new Error('Invalid groupBy input type');
  }
  const newGroupedNode: {[key: string]: Types.Node} = {};
  for (const key of Object.keys(groupedNode)) {
    newGroupedNode[key] = Op.opPick({
      obj: Graph.varNode(unnestedType.objectType, 'row'),
      key: Op.constString(key),
    });
  }
  node = Op.opGroupby({
    arr: node as any,
    groupByFn: Op.defineFunction({row: getExampleRow(node).type}, ({row}) =>
      Op.opDict(newGroupedNode as any)
    ) as any,
  });
  return node;
}

function groupByNodeForRegularStyle(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  node: Types.Node<Types.Type>
) {
  const groupedNode: {[key: string]: Types.Node} = groupDict(
    order,
    groupByColumns,
    columnSelectFunctions,
    columnNames
  );
  node = Op.opGroupby({
    arr: node as any,
    // Variable name must be row for now!
    groupByFn: Op.defineFunction({row: getExampleRow(node).type}, row =>
      Op.opDict(groupedNode as any)
    ),
  });
  return node;
}

function sortNodeForRegularStyle(
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  groupByColumns: GroupByColumns,
  sortByColumns: Sort[],
  node: Types.Node<Types.Type>
) {
  const compFn = getComparableDataFn(
    columnSelectFunctions,
    columnNames,
    groupByColumns,
    sortByColumns,
    node
  );
  if (compFn.nodeType !== 'void') {
    node = Op.opSort({
      arr: node as any,
      compFn: Op.defineFunction(
        {row: getExampleRow(node).type},
        ({row}) => compFn
      ),
      columnDirs: Op.constNodeUnsafe(
        {type: 'list', objectType: 'string'},
        sortByColumns.map(sort => sort.dir)
      ),
    });
  }
  return node;
}

export function getRowsNode(
  preFilterFunction: Types.NodeOrVoidNode,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  order: ColumnOrder,
  sortByColumns: Sort[],
  inputNode: Types.Node
) {
  let node = inputNode;

  // pre-filter
  if (preFilterFunction.nodeType === 'output') {
    node = Op.opFilter({
      arr: node as any,
      filterFn: Op.defineFunction(
        {row: getExampleRow(node).type},
        // Variable name must be row in preFilterFunction for now!
        row => preFilterFunction
      ) as any,
    });
  }

  // group
  if (groupByColumns.length > 0) {
    if (needsUnnestQuery(groupByColumns, columnSelectFunctions)) {
      node = groupByNodeForUnnestStyle(
        order,
        groupByColumns,
        columnSelectFunctions,
        columnNames,
        node
      );
    } else {
      node = groupByNodeForRegularStyle(
        order,
        groupByColumns,
        columnSelectFunctions,
        columnNames,
        node
      );
    }
  }

  // sort
  if (sortByColumns.length > 0) {
    if (needsUnnestQuery(groupByColumns, columnSelectFunctions)) {
      throw new Error('sort for unnest style query not yet implemented');
    } else {
      node = sortNodeForRegularStyle(
        columnSelectFunctions,
        columnNames,
        groupByColumns,
        sortByColumns,
        node
      );
    }
  }

  return node;
}

export function getTableColumnName(
  columnNames: {[colId: string]: string},
  columnSelectFunctions: ColumnSelectFunctions,
  colId: ColumnId
) {
  const name =
    columnNames[colId] !== ''
      ? columnNames[colId]
      : HL.simpleNodeString(columnSelectFunctions[colId]);
  if (name == null) {
    throw new Error('invalid table state');
  }
  return name;
}

function selectFnUnnestStyle(
  exampleRowNode: Types.Node,
  columnSelectFn: Types.Node,
  colName: string
) {
  const unagged = getUnaggedAncestor(columnSelectFn);
  if (unagged != null) {
    const newSelFn = HL.replaceNode(
      columnSelectFn,
      unagged,
      Op.opPick({
        obj: Graph.varNode(exampleRowNode.type, 'row') as any,
        key: Op.constString(colName),
      })
    );
    newSelFn.type = columnSelectFn.type;
    return newSelFn as Types.Node;
  }
  return Op.opPick({
    obj: Graph.varNode(exampleRowNode.type, 'row') as any,
    key: Op.constString(colName),
  });
}

function getResultTableNodeUnnestStyle(
  rowsNode: Types.Node,
  exampleRowNode: Types.Node,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  groupByColumns: GroupByColumns,
  order: ColumnOrder
) {
  const metricNodes: {[key: string]: Types.Node} = {};
  // For ungrouped columns, we split the node at the point
  // where aggregation starts. Here we use the aggregation part.
  for (const colId of order) {
    if (!groupByColumns.includes(colId)) {
      const columnSelectFn = columnSelectFunctions[colId];
      if (columnSelectFn.nodeType !== 'void') {
        const colName = getTableColumnName(
          columnNames,
          columnSelectFunctions,
          colId
        );
        metricNodes[colName] = selectFnUnnestStyle(
          exampleRowNode,
          columnSelectFn,
          colName
        );
      }
    }
  }
  return Op.opMap({
    arr: rowsNode as any,
    mapFn: Op.defineFunction({row: exampleRowNode.type}, ({row}) =>
      Op.opMerge({
        lhs:
          Object.keys(groupByColumns).length > 0
            ? Op.opGroupGroupKey({
                obj: row,
              })
            : Op.opDict({} as any),
        rhs: Op.opDict(metricNodes as any),
      } as any)
    ),
  } as any);
}

function resultTableNodeRegularStyle(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  rowsNode: Types.Node<Types.Type>,
  exampleRowNode: Types.OutputNode<Types.Type>
) {
  const metricNodes: {[key: string]: Types.Node} = {};
  for (const colId of order) {
    if (!groupByColumns.includes(colId)) {
      const selectFn = columnSelectFunctions[colId];
      if (selectFn.type !== 'invalid') {
        const colName = getTableColumnName(
          columnNames,
          columnSelectFunctions,
          colId
        );
        metricNodes[colName] = selectFn;
      }
    }
  }
  return Op.opMap({
    arr: rowsNode as any,
    mapFn: Op.defineFunction(
      {row: exampleRowNode.type, index: 'number'},
      ({row, index}) =>
        Op.opMerge({
          lhs:
            Object.keys(groupByColumns).length > 0
              ? Op.opGroupGroupKey({
                  obj: row,
                })
              : Op.opDict({} as any),
          rhs: Op.opDict({...metricNodes, _index: index} as any),
        } as any)
    ),
  } as any);
}

export function getResultTableNode(
  rowsNode: Types.Node,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  groupByColumns: GroupByColumns,
  order: ColumnOrder
) {
  if (!Object.values(columnSelectFunctions).some(n => n.type !== 'invalid')) {
    return Op.constNodeUnsafe(
      {
        type: 'list',
        objectType: {
          type: 'typedDict',
          propertyTypes: {},
        },
      },
      []
    );
  }
  const exampleRowNode = getExampleRow(rowsNode);
  // console.log('ROWS NODE', exampleRowNode.type);

  if (needsUnnestQuery(groupByColumns, columnSelectFunctions)) {
    return getResultTableNodeUnnestStyle(
      rowsNode,
      exampleRowNode,
      columnSelectFunctions,
      columnNames,
      groupByColumns,
      order
    );
  } else {
    return resultTableNodeRegularStyle(
      order,
      groupByColumns,
      columnSelectFunctions,
      columnNames,
      rowsNode,
      exampleRowNode
    );
  }
}

export function tableGetResultTableNode(
  tableState: TableState,
  inputNode: Types.Node,
  frame: Code.Frame
) {
  const exampleInputFrame = getRowFrame(inputNode, frame);

  const rowsNode = getRowsNode(
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    inputNode
  );
  const resultNode = getResultTableNode(
    rowsNode,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.groupBy,
    tableState.order
  );

  const {node} = HL.dereferenceVariables(resultNode, frame);
  const dereffed = node as typeof resultNode;

  return {exampleInputFrame, rowsNode, resultNode: dereffed};
}

// Return the type of resultNode as returned by tableGetResultTableNode above.
export const getTableColType = (
  tableConfig: TableState,
  colId: string
): Types.Type => {
  const selFn = tableConfig.columnSelectFunctions[colId];
  if (selFn.type === 'invalid') {
    return 'invalid';
  }
  return selFn.type;
};

// This is only used in tests currently. Its inefficient, computes the
// dict version first and then converts to an array. We could do that
// in a single shot instead.
export function tableGetResultTableArrayRowsNode(
  tableState: TableState,
  inputNode: Types.Node,
  frame: Code.Frame
) {
  const {resultNode} = tableGetResultTableNode(tableState, inputNode, frame);

  const metricNodes: {[key: string]: Types.Node} = {};
  for (const colId of tableState.groupBy.concat(
    tableState.order.filter(cid => !tableState.groupBy.includes(cid))
  )) {
    const selectFn = tableState.columnSelectFunctions[colId];
    if (selectFn.type !== 'invalid') {
      const colName = getTableColumnName(
        tableState.columnNames,
        tableState.columnSelectFunctions,
        colId
      );
      metricNodes[colName] = Op.opPick({
        obj: Graph.varNode('any', 'row'),
        key: Op.constString(colName),
      });
    }
  }
  const finalResult = Op.opMap({
    arr: resultNode,
    mapFn: Op.defineFunction({row: getExampleRow(resultNode).type}, ({row}) =>
      Op.opArray(metricNodes as any)
    ) as any,
  });
  return finalResult;
}

export async function getColumnDomainRanges(
  client: Client,
  ts: TableState,
  inputNode: Types.Node,
  frame: Code.Frame
) {
  // TODO: Make this function do the right thing when we don't
  // already have a frame.domain!
  // let domainNode = inputNode;
  // let domainVar = Graph.varNode(inputNode.type, 'input');
  // let domainFrame: Code.Frame = {
  //   ...frame,
  //   input: inputNode,
  // };
  if (frame.domain == null) {
    return {
      rangeColFns: {},
      executableRangesNode: Graph.voidNode(),
    };
  }
  const domainNode = frame.domain;
  const domainVar = Graph.varNode(inputNode.type, 'domain');
  const domainFrame = frame;
  const domainColSelFnPromises = _.map(
    ts.columnSelectFunctions,
    (selFn, colId) => {
      if (selFn.nodeType === 'void') {
        return Promise.resolve(Graph.voidNode());
      }
      const appliedSelFn = Op.opFlatten({
        arr: Op.opMap({
          arr: domainVar,
          mapFn: Op.defineFunction(
            {row: getExampleRow(domainNode).type as any},
            ({row}) => {
              const siblingRows = getRowsNode(
                ts.preFilterFunction,
                ts.groupBy,
                ts.columnSelectFunctions,
                ts.columnNames,
                ts.order,
                ts.sort,
                row
              );
              return Op.opMap({
                arr: siblingRows,
                mapFn: Op.defineFunction({row: siblingRows.type}, ({row}) =>
                  ts.groupBy.includes(colId)
                    ? Op.opPick({
                        obj: Op.opGroupGroupKey({obj: row}),
                        key: Op.constString(
                          Op.escapeDots(
                            getTableColumnName(
                              ts.columnNames,
                              ts.columnSelectFunctions,
                              colId
                            )
                          )
                        ),
                      })
                    : HL.callFunction(selFn, {row})
                ) as any,
              });
            }
          ),
        }) as any,
      });
      return HL.updateFunctionForInputs(client, appliedSelFn, domainFrame);
    }
  );
  const domainColSelFns = await Promise.all(
    domainColSelFnPromises as Array<Promise<Types.Node>>
  );
  const colIds = _.keys(ts.columnSelectFunctions);
  const rangeColFns: {[colId: string]: Types.Node} = {};
  for (let i = 0; i < colIds.length; i++) {
    const colId = colIds[i];
    const domainColSelFn = domainColSelFns[i];
    const colSelType = ts.columnSelectFunctions[colId].type;
    if (Types.isAssignableTo2(colSelType, Types.maybe('number'))) {
      rangeColFns[colId] = Op.opDict({
        start: Op.opNumbersMin({numbers: domainColSelFn as any}),
        end: Op.opNumbersMax({numbers: domainColSelFn as any}),
      } as any);
    } else if (Types.isAssignableTo2(colSelType, Types.maybe('string'))) {
      rangeColFns[colId] = Op.opUnique({arr: domainColSelFn as any});
    }
  }

  const executableRangesNode = Op.opDict(
    _.mapValues(rangeColFns, rangeColFn =>
      HL.callFunction(rangeColFn, domainFrame)
    ) as any
  );

  return {rangeColFns, executableRangesNode};
}

export function getCellValueNode(
  rowNode: Types.Node,
  selectFunction: Types.NodeOrVoidNode
) {
  if (selectFunction.nodeType === 'void') {
    return selectFunction;
  }
  return HL.callFunction(selectFunction, {row: rowNode});
}

export function addColumnToTable(
  table: TableState,
  selectFn: Types.NodeOrVoidNode<Types.Type>
): {table: TableState; columnId: string} {
  table = appendEmptyColumn(table);
  const columnId = table.order[table.order.length - 1];
  table = updateColumnSelect(table, columnId, selectFn);

  return {table, columnId};
}

export type AddColumnEntries = Array<{
  selectFn: Types.NodeOrVoidNode;
  keyName: string;
}>;

// To batch above, need to unroll the inner fn calls
// Much more efficient when we are adding potentially thousands of columns to a table
export function addColumnsToTable(ts: TableState, colData: AddColumnEntries) {
  const newColIds: string[] = [];
  const table = produce(ts, draft => {
    draft.autoColumns = false;

    for (const col of colData) {
      newColIds.push(addColumnToDraft(draft, col.keyName, col.selectFn));
    }
  });
  return {table, columnIds: newColIds};
}

export function addNamedColumnToTable(
  table: TableState,
  name: string,
  selectFn: Types.NodeOrVoidNode<Types.Type>
): TableState {
  table = appendEmptyColumn(table);
  const columnId = table.order[table.order.length - 1];
  table = updateColumnSelect(table, columnId, selectFn);
  table = updateColumnName(table, columnId, name);
  return table;
}

// TableEditor compatibility
// TODO: consolidate these w/ existing functions in this module

export const COLUMN_LIMIT = 100;

export interface ColumnEntry {
  name: string;

  // Only visible columns have an ID
  id?: string;

  selectFn?: Types.NodeOrVoidNode;
}

function addColumnToDraft(
  draft: TableState,
  key: string,
  selectFn: Types.NodeOrVoidNode
) {
  const colId = newColumnId();
  draft.order.push(colId);
  draft.columns[colId] = {
    panelId: '',
    panelConfig: undefined,
    originalKey: key,
  };
  draft.columnNames[colId] = key;
  draft.columnSelectFunctions[colId] = selectFn;

  return colId;
}

export function addColumns(
  table: TableState,
  colsToShow: ColumnEntry[]
): TableState {
  // BUG: column names are not unique, so we could have a collision
  // here and always map the provided column name to the last ID
  // in the mapping
  const nameToIdMap = Object.entries(table.columnNames).reduce<
    Map<string, string>
  >((memo, [colId, colName]) => {
    return memo.set(colName, colId);
  }, new Map());

  table = produce(table, draft => {
    for (const col of colsToShow) {
      const colId = col.id ?? nameToIdMap.get(col.name);

      if (colId == null) {
        // Not an existing column
        if (col.selectFn == null) {
          throw new Error(
            `select fn not provided for column named "${col.name}"`
          );
        }
        addColumnToDraft(draft, col.name, col.selectFn as any);
      } else if (!draft.order.includes(colId)) {
        // Exists but not found in order
        draft.order.push(colId);
      }
    }

    draft.autoColumns = false;
  });

  return table;
}
export function removeColumns(
  table: TableState,
  colsToHide: ColumnEntry[]
): TableState {
  table = produce(table, draft => {
    const colIdsToRemove = Object.entries(draft.columns).reduce<string[]>(
      (memo, [colId, col]) => {
        if (colsToHide.some(hideCol => hideCol.id === colId)) {
          memo.push(colId);
        }

        return memo;
      },
      []
    );

    draft.order = draft.order.filter(colId => !colIdsToRemove.includes(colId));
    draft.groupBy = draft.groupBy.filter(
      colId => !colIdsToRemove.includes(colId)
    );
    draft.autoColumns = false;
  });

  return table;
}

export function moveBefore(
  table: TableState,
  moveCol: ColumnEntry,
  beforeCol: ColumnEntry
): TableState {
  if (moveCol.id == null) {
    return table;
  }

  const indexOfMoveCol = table.order.findIndex(id => id === moveCol.id);
  const indexOfBeforeCol = table.order.findIndex(id => id === beforeCol.id);
  if (indexOfMoveCol !== -1 && indexOfBeforeCol !== -1) {
    return produce(table, draft => {
      draft.order.splice(indexOfMoveCol, 1);
      draft.order.splice(indexOfBeforeCol, 0, moveCol.id!);
      draft.autoColumns = false;
    });
  }
  return table;
}

export function moveToEnd(table: TableState, col: ColumnEntry): TableState {
  const indexOfMoveCol = table.order.findIndex(id => id === col.id);
  if (indexOfMoveCol !== -1) {
    return produce(table, draft => {
      draft.order.push(draft.order.splice(indexOfMoveCol, 1)[0]);
      draft.autoColumns = false;
    });
  }

  return table;
}
