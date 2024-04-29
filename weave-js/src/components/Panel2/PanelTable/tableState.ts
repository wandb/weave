import {
  allObjPaths,
  constFunction,
  ConstNode,
  constNodeUnsafe,
  constNumber,
  constString,
  dereferenceAllVars,
  escapeDots,
  filterNodes,
  Frame,
  isAssignableTo,
  isFunction,
  isList,
  isListLike,
  isSimpleTypeShape,
  listObjectType,
  maybe,
  Node,
  NodeOrVoidNode,
  nonNullable,
  nullableTaggableValue,
  Op,
  opArray,
  opDict,
  opFilter,
  opFlatten,
  opGetJoinedJoinObj,
  opGroupby,
  opGroupGroupKey,
  opIndex,
  opLimit,
  opMap,
  opMerge,
  opNumbersMax,
  opNumbersMin,
  opObjGetAttr,
  opOffset,
  opPick,
  opSort,
  OpStore,
  opUnique,
  OutputNode,
  PathType,
  pushFrame,
  refineNode,
  resolveVar,
  rootObject,
  simpleNodeString,
  Stack,
  Type,
  typedDict,
  varNode,
  voidNode,
  WeaveInterface,
} from '@wandb/weave/core';
import {produce} from 'immer';
import _ from 'lodash';

export type ColumnId = string;

interface TableColumnPanel {
  panelVars?: {[id: string]: NodeOrVoidNode};
  panelId: string;
  panelConfig: any;

  // For columns that are simple property keys
  // Need this to construct the set: {hiddenKeys} = {allKeys} - {visibleKeys}
  originalKey?: any;
}

interface Sort {
  dir: 'asc' | 'desc';
  columnId: ColumnId;
}

type ColumnSelectFunctions = {
  [id: string]: NodeOrVoidNode;
};

type ColumnOrder = ColumnId[];
type GroupByColumns = ColumnId[];

export interface TableState {
  autoColumns: boolean;
  columns: {
    [id: string]: TableColumnPanel;
  };

  preFilterFunction: NodeOrVoidNode;

  // A table's rows node depends on the filters,
  // which depend on the column filter and select functions.
  // Store them separately from the table column panel config,
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

function newColumnId(ts: TableState) {
  for (let i = 0; i < 1000; i++) {
    const id = 'col-' + i.toString();
    if (!(id in ts.columns)) {
      return id;
    }
  }
  throw new Error('Could not find a new column id');
}

export function emptyTable(): TableState {
  return {
    autoColumns: true,
    columns: {},
    columnNames: {},
    preFilterFunction: voidNode(),
    columnSelectFunctions: {},
    order: [],
    groupBy: [],
    sort: [],
    pageSize: 10,
    page: 0,
  };
}

export function initTableWithPickColumns(
  inputArrayNode: Node,
  weave: WeaveInterface,
  pickColumns?: string[]
) {
  const arrayType = inputArrayNode.type;
  let addCols: AddColumnEntries = [];
  let allColumns: Node[] = [];
  const objectType = listObjectType(arrayType);

  let ts = emptyTable();
  const exNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );

  const listIndexWithStar =
    filterNodes(inputArrayNode, n => {
      return n.nodeType === 'output' && n.fromOp.name.endsWith('joinAll');
    }).length > 0;

  if (pickColumns) {
    addCols = pickColumns.map(colKey => ({
      selectFn: opPick({
        obj: varNode(exNode.type, 'row') as any,
        key: constString(colKey),
      }),
      keyName: colKey,
    }));
  } else {
    if (
      isAssignableTo(nonNullable(objectType), {
        type: 'union',
        members: [typedDict({}), rootObject()],
      })
    ) {
      allColumns = autoTableColumnExpressions(exNode.type, objectType, {
        listIndexWithStar,
      });
    }
    const columns =
      allColumns.length > 100 ? allColumns.slice(0, 100) : allColumns;
    if (columns.length === 0) {
      // If no columns are provided, at least fill it with a general row column.
      ts = addColumnToTable(ts, varNode(exNode.type, 'row')).table;
    } else {
      addCols = columns.map(colExpr => ({
        selectFn: colExpr,
        keyName: '',
      }));
    }
  }
  ts = addColumnsToTable(ts, addCols).table;
  return ts;
}

function isNDArrayLike(type: Type): boolean {
  type = nullableTaggableValue(type);
  if (isSimpleTypeShape(type)) {
    return false;
  } else if (type.type === 'ndarray') {
    return true;
  } else if (isListLike(type)) {
    return isNDArrayLike(listObjectType(type));
  }
  return false;
}

const streamTableColumns = [
  // Added by Stream Table
  'timestamp',
  '_client_id',
  // Added by Run
  '_timestamp',
  // Added by Gorilla
  '_step',
];
const monitoringColumns = [
  // Added by monitor decorator
  'result_id',
  'inputs',
  'output',
  'latency_ms',
  'start_datetime',
  'end_datetime',
  'exception',
  ...streamTableColumns,
];

const excludedStreamTableColumns = [
  '_client_id',
  // Added by Run
  '_timestamp',
  // Added by Gorilla
  '_step',
];

const excludedMonitoringColumns = ['timestamp', ...excludedStreamTableColumns];

function allPathsFromMonitoring(allPaths: PathType[]): boolean {
  for (const col of monitoringColumns) {
    if (!allPaths.find(p => p.path[0] === col)) {
      return false;
    }
  }
  return true;
}

function allPathsFromStreamTable(allPaths: PathType[]): boolean {
  for (const col of streamTableColumns) {
    if (!allPaths.find(p => p.path[0] === col)) {
      return false;
    }
  }
  return true;
}

// Try to pick nice default columns to make a table for the given object
// type. See the initial columns test in tableState.test.ts to see examples
// of current behavior.
export function autoTableColumnExpressions(
  tableRowType: Type,
  objectType: Type,
  opts: {
    listIndexWithStar: boolean;
  } = {
    listIndexWithStar: true,
  }
): Node[] {
  const {listIndexWithStar} = opts;
  let allPaths = allObjPaths(objectType).filter(
    path => !isNDArrayLike(path.type) && !isAssignableTo(path.type, 'none')
  );

  if (allPathsFromMonitoring(allPaths)) {
    allPaths = allPaths.filter(
      p => !excludedMonitoringColumns.includes(p.path[0])
    );
    allPaths = allPaths.sort((a, b) => {
      const aIdx = monitoringColumns.indexOf(a.path[0]);
      const bIdx = monitoringColumns.indexOf(b.path[0]);
      return aIdx - bIdx;
    });
  } else if (allPathsFromStreamTable(allPaths)) {
    allPaths = allPaths.filter(
      p => !excludedStreamTableColumns.includes(p.path[0])
    );
  }

  return allPaths
    .map(pt => pt.path.map(escapeDots))
    .map(path => {
      let expr: Node = varNode(tableRowType, 'row');
      let pathStr: string[] = [];
      const finishPick = () => {
        if (pathStr.length > 0) {
          expr = opPick({
            obj: expr,
            key: constString(pathStr.join('.')),
          });
          // We have to reset the pathStr after collapsing it into an opPick!
          pathStr = [];
        }
      };
      for (const p of path) {
        if (p.startsWith('__object')) {
          finishPick();
          expr = opObjGetAttr({
            self: expr,
            name: constString(p.slice('__object__'.length)),
          });
        } else if (p === '*' && !listIndexWithStar) {
          finishPick();
          expr = opIndex({
            arr: expr,
            index: constNumber(-1),
          });
        } else {
          pathStr.push(p);
        }
      }
      if (pathStr.length > 0) {
        expr = opPick({
          obj: expr,
          key: constString(pathStr.join('.')),
        });
      }
      return expr;
    });
}

// Given a row node that we're going to render as a table, try to
// pick a good set of default columns.
// This doesn't really have enough information to do a great job.
// We may want to call it from WBJoinedTable and WBTable instead
// of PanelTable, where we no longer have a table and just have an
// array of objects. Or we could walk up the graph from here to
// determine where our array came from...
export function initTableFromTableType(
  inputArrayNode: Node,
  weave: WeaveInterface
) {
  let table = initTableWithPickColumns(inputArrayNode, weave);
  table = maybeAddCompareColumn(table, inputArrayNode, weave);
  table = setAutoColumns(table, true);
  return {table};
}

function maybeAddCompareColumn(
  table: TableState,
  inputNode: Node,
  weave: WeaveInterface
) {
  if (inputNode.nodeType === 'output' && inputNode.fromOp.name === 'joinAll') {
    const joinObjNode = opGetJoinedJoinObj({
      obj: varNode(getExampleRow(inputNode).type, 'row'),
    });
    if (joinObjNode.type !== 'invalid' && joinObjNode.type !== 'none') {
      table = prependColumn(table, inputNode, weave);
      table = updateColumnSelect(table, table.order[0], joinObjNode);
      table = updateColumnName(table, table.order[0], 'Joined On');
      table = setAutoColumns(table, true);
    }

    let joinedOnKeys: string[] = [];
    if (
      inputNode.fromOp.inputs.joinFn.nodeType === 'const' &&
      isFunction(inputNode.fromOp.inputs.joinFn.type)
    ) {
      const fnOp = inputNode.fromOp.inputs.joinFn.val.fromOp as Op;
      if (fnOp.name === 'pick') {
        const keyNode = fnOp.inputs.key;
        if (keyNode.nodeType === 'const') {
          joinedOnKeys = [keyNode.val];
        }
      } else if (fnOp.name === 'none-coalesce') {
        let coalesceOp: Op | null = fnOp;
        while (coalesceOp != null) {
          const rhsNode = coalesceOp.inputs.rhs;
          if (rhsNode.nodeType === 'output' && rhsNode.fromOp.name === 'pick') {
            const rhsNodeKeyNode = rhsNode.fromOp.inputs.key;
            if (rhsNodeKeyNode.nodeType === 'const') {
              joinedOnKeys.push(rhsNodeKeyNode.val);
            }
          }
          const lhsNode: Node = coalesceOp.inputs.lhs;
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
            (selectFn.fromOp.inputs.key as ConstNode).val as string
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

export function tableColumnsDiff(
  weave: WeaveInterface,
  toTable: TableState,
  fromTable?: TableState
) {
  const toTableCols = new Set<string>();
  const fromTableCols = new Set<string>();

  for (const colSelFn of Object.values(toTable.columnSelectFunctions)) {
    toTableCols.add(weave.expToString(colSelFn));
  }
  if (fromTable != null && fromTable.columnNames != null) {
    for (const colSelFn of Object.values(fromTable.columnSelectFunctions)) {
      fromTableCols.add(weave.expToString(colSelFn));
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

export function appendEmptyColumn(
  ts: TableState,
  index?: number,
  customId?: string
) {
  const colId = customId
    ? customId
    : index == null
    ? newColumnId(ts)
    : `col-${index}`;
  return produce(ts, draft => {
    draft.columns[colId] = {
      panelId: '',
      panelConfig: undefined,
    };
    draft.columnNames[colId] = '';
    draft.columnSelectFunctions[colId] = voidNode();
    draft.order.push(colId);
  });
}

export function appendColumn(
  ts: TableState,
  inputNode: Node,
  weave: WeaveInterface
) {
  const colId = newColumnId(ts);
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputNode,
    weave
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[colId] = {
      panelId: '',
      panelConfig: undefined,
    };
    draft.columnNames[colId] = '';
    draft.columnSelectFunctions[colId] = varNode(rowExampleNode.type, 'row');
    draft.order.push(colId);
  });
}

export function prependColumn(
  ts: TableState,
  inputNode: Node,
  weave: WeaveInterface
) {
  const colId = newColumnId(ts);
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputNode,
    weave
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[colId] = {
      panelId: '',
      panelConfig: undefined,
    };
    draft.columnNames[colId] = '';
    draft.columnSelectFunctions[colId] = varNode(rowExampleNode.type, 'row');
    draft.order.unshift(colId);
  });
}

export function setAutoColumns(ts: TableState, autoColumns: boolean) {
  return produce(ts, draft => {
    draft.autoColumns = autoColumns;
  });
}

export function updatePreFilter(ts: TableState, filterFn: NodeOrVoidNode) {
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
  selectFn: NodeOrVoidNode
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
  ts: TableState,
  colId: string,
  inputArrayNode: Node,
  weave: WeaveInterface,
  stack: Stack
) {
  ts = produce(ts, draft => {
    draft.autoColumns = false;
    if (ts.columns[colId] == null) {
      throw new Error('invalid group by col id' + colId);
    }
    if (ts.groupBy.includes(colId)) {
      return;
    }
    draft.groupBy.push(colId);
  });
  ts = await refreshSelectFunctions(ts, inputArrayNode, weave, stack);
  // Disable prior sort as it does not make sense to sort on lists of things
  ts = disableSort(ts);
  // we sort by the first group by key to ensure they stay together
  // TODO: if the user groups by more than 2 columns, we should
  // sort by all but the last column
  ts = enableSortByCol(ts, ts.groupBy[0], true);
  return ts;
}

export async function disableGroupByCol(
  ts: TableState,
  colId: string,
  inputArrayNode: Node,
  weave: WeaveInterface,
  stack: Stack
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
  ts = await refreshSelectFunctions(ts, inputArrayNode, weave, stack);
  if (ts.sort.find(s => s.columnId === colId) !== undefined) {
    ts = disableSortByCol(ts, colId);
  }
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
  inputArrayNode: Node,
  weave: WeaveInterface
) {
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid insert col id' + colId);
  }

  const newColId = newColumnId(ts);
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[newColId] = {
      panelId: '',
      panelConfig: {},
    };
    draft.columnNames[newColId] = '';
    draft.columnSelectFunctions[newColId] = varNode(rowExampleNode.type, 'row');
    draft.order.splice(colIndex + 1, 0, newColId);
  });
}

export function insertColumnLeft(
  ts: TableState,
  colId: string,
  inputArrayNode: Node,
  weave: WeaveInterface
) {
  const colIndex = ts.order.indexOf(colId);
  if (colIndex === -1) {
    throw new Error('invalid insert col id' + colId);
  }

  const newColId = newColumnId(ts);
  const rowExampleNode = getRowExampleNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );
  return produce(ts, draft => {
    draft.autoColumns = false;
    draft.columns[newColId] = {
      panelId: '',
      panelConfig: {},
    };
    draft.columnNames[newColId] = '';
    draft.columnSelectFunctions[newColId] = varNode(rowExampleNode.type, 'row');
    draft.order.splice(colIndex, 0, newColId);
  });
}

export function removeColumn(ts: TableState, colId: string) {
  if (ts.groupBy.includes(colId)) {
    // We don't allow removing the group by column. The UI
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

export function getRowFrame(inputNode: Node) {
  return {
    row: getExampleRow(inputNode),
    // Don't include index in frame for now. We don't need it yet.
    index: varNode('number', 'index'),
    // Don't include arr in frame for now. We don't need it yet and
    // need to fix suggest ordering before including it.
    // arr: inputNode,
  };
}

export async function refreshSelectFunctions(
  ts: TableState,
  inputArrayNode: Node,
  weave: WeaveInterface,
  stack: Stack
) {
  const rowsNode = getRowsNode(
    ts.preFilterFunction,
    ts.groupBy,
    ts.columnSelectFunctions,
    ts.columnNames,
    ts.order,
    ts.sort,
    inputArrayNode,
    weave
  );
  const cols = ts.order;
  const newSelectFns = await Promise.all(
    cols.map(colId => {
      const cellFrame = getCellFrame(
        inputArrayNode,
        rowsNode,
        ts.groupBy,
        ts.columnSelectFunctions,
        colId
      );
      const colSelectFn = ts.columnSelectFunctions[colId];
      if (colSelectFn.nodeType === 'void') {
        return Promise.resolve(voidNode());
      }
      return refineNode(
        weave.client,
        colSelectFn,
        pushFrame(stack, cellFrame)
      ) as Promise<NodeOrVoidNode>;
    })
  );
  cols.forEach(
    (colId, i) => (ts = updateColumnSelect(ts, colId, newSelectFns[i]))
  );
  return ts;
}

export function getCellFrame(
  inputNode: Node,
  rowsNode: Node,
  groupByColumns: ColumnId[],
  columnSelectFunctions: ColumnSelectFunctions,
  colId: string
) {
  // In the normal case, we select from an example row from input.
  let exampleNode: Node;

  if (
    isGrouped(groupByColumns, columnSelectFunctions) &&
    !groupByColumns.includes(colId)
  ) {
    exampleNode = getExampleRow(rowsNode);
  } else {
    exampleNode = getExampleRow(inputNode);
  }
  const newFrame: Frame = isList(inputNode.type)
    ? {
        row: exampleNode,
        index: varNode('number', 'index'),
        // Don't include arr in frame for now. We don't need it yet and
        // need to fix suggest ordering before including it.
        // arr: inputNode,
      }
    : {
        row: exampleNode,
        index: varNode('number', 'index'),
        // key: varNode('string', 'key'),
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

export function getColumnRenderOrder(tableState: TableState) {
  return tableState.order.filter(colId => !tableState.groupBy.includes(colId));
}

export function getExampleRow(exampleRowsNode: NodeOrVoidNode) {
  return opIndex({
    arr: exampleRowsNode as any,
    index: varNode('number', 'n'),
  });
}

export function getRowExampleNode(
  preFilterFunction: NodeOrVoidNode,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  order: ColumnOrder,
  sortByColumns: Sort[],
  inputArrayNode: Node,
  weave: WeaveInterface
) {
  const visibleRowsNode = getRowsNode(
    preFilterFunction,
    groupByColumns,
    columnSelectFunctions,
    columnNames,
    order,
    sortByColumns,
    inputArrayNode,
    weave
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
  inputNode: Node,
  weave: WeaveInterface
) {
  const exampleRowNode = opIndex({
    arr: inputNode as any,
    index: varNode('number', 'n'),
  });

  if (sortBy.length === 0) {
    throw new Error('Invalid sortBy value');
  }

  const colVals: {[key: string]: Node} = {};
  for (const sort of sortBy) {
    const colSelectFunction = columnSelectFunctions[sort.columnId];
    let colVal: Node = varNode(exampleRowNode.type, 'row');
    if (colSelectFunction.nodeType !== 'void') {
      if (groupBy.includes(sort.columnId)) {
        colVal = opPick({
          obj: opGroupGroupKey({obj: colVal}),
          key: constString(
            getTableColumnName(
              columnNames,
              columnSelectFunctions,
              sort.columnId,
              weave.client.opStore
            )
          ),
        });
      } else {
        colVal = weave.callFunction(colSelectFunction, {
          row: colVal as any,
        });
      }
    }
    colVals[sort.columnId] = colVal;
  }
  if (Object.keys(colVals).length === 0) {
    return voidNode();
  }
  return opArray(colVals as any);
}

export function getPagedRowsNode(
  pageSize: number,
  page: number,
  rowsNode: Node
) {
  let node = opOffset({
    arr: rowsNode as any,
    offset: constNumber(pageSize * page),
  });
  node = opLimit({
    arr: node as any,
    limit: constNumber(pageSize),
  });
  return node;
}

function groupDict(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  opStore: OpStore
) {
  const groupedNode: {[key: string]: Node} = {};
  for (const colId of order) {
    if (groupByColumns.includes(colId)) {
      const selectFn = columnSelectFunctions[colId];
      if (selectFn.type !== 'invalid') {
        const colName = getTableColumnName(
          columnNames,
          columnSelectFunctions,
          colId,
          opStore
        );
        groupedNode[colName] = selectFn;
      }
    }
  }
  return groupedNode;
}

function groupByNodeForRegularStyle(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  node: Node<Type>,
  opStore: OpStore
) {
  const groupedNode: {[key: string]: Node} = groupDict(
    order,
    groupByColumns,
    columnSelectFunctions,
    columnNames,
    opStore
  );
  node = opGroupby({
    arr: node as any,
    // Variable name must be row for now!
    groupByFn: constFunction({row: getExampleRow(node).type}, row =>
      opDict(groupedNode as any)
    ),
  });
  return node;
}

function sortNodeForRegularStyle(
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  groupByColumns: GroupByColumns,
  sortByColumns: Sort[],
  node: Node<Type>,
  weave: WeaveInterface
) {
  const compFn = getComparableDataFn(
    columnSelectFunctions,
    columnNames,
    groupByColumns,
    sortByColumns,
    node,
    weave
  );
  if (compFn.nodeType !== 'void') {
    node = opSort({
      arr: node as any,
      compFn: constFunction({row: getExampleRow(node).type}, ({row}) => compFn),
      columnDirs: constNodeUnsafe(
        {type: 'list', objectType: 'string'},
        sortByColumns.map(sort => sort.dir)
      ),
    });
  }
  return node;
}

export function getRowsNode(
  preFilterFunction: NodeOrVoidNode,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  order: ColumnOrder,
  sortByColumns: Sort[],
  inputNode: Node,
  weave: WeaveInterface
) {
  let node = inputNode;

  // pre-filter
  if (preFilterFunction.nodeType === 'output') {
    node = opFilter({
      arr: node as any,
      filterFn: constFunction(
        {row: getExampleRow(node).type},
        // Variable name must be row in preFilterFunction for now!
        row => preFilterFunction
      ) as any,
    });
  }

  // group
  if (groupByColumns.length > 0) {
    node = groupByNodeForRegularStyle(
      order,
      groupByColumns,
      columnSelectFunctions,
      columnNames,
      node,
      weave.client.opStore
    );
  }

  // Sort
  if (sortByColumns.length > 0) {
    node = sortNodeForRegularStyle(
      columnSelectFunctions,
      columnNames,
      groupByColumns,
      sortByColumns,
      node,
      weave
    );
  }

  return node;
}

export function getTableColumnName(
  columnNames: {[colId: string]: string},
  columnSelectFunctions: ColumnSelectFunctions,
  colId: ColumnId,
  opStore: OpStore
) {
  const name =
    columnNames[colId] !== ''
      ? columnNames[colId]
      : simpleNodeString(columnSelectFunctions[colId], opStore);
  if (name == null) {
    throw new Error('invalid table state');
  }
  return name;
}

export const allTableColumnNames = (
  tableState: TableState,
  opStore: OpStore
) => {
  return tableState.order.map(colId =>
    getTableColumnName(
      tableState.columnNames,
      tableState.columnSelectFunctions,
      colId,
      opStore
    )
  );
};

function resultTableNodeRegularStyle(
  order: ColumnOrder,
  groupByColumns: GroupByColumns,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  rowsNode: Node<Type>,
  exampleRowNode: OutputNode<Type>,
  opStore: OpStore
) {
  const metricNodes: {[key: string]: Node} = {};
  for (const colId of order) {
    if (!groupByColumns.includes(colId)) {
      const selectFn = columnSelectFunctions[colId];
      if (selectFn.type !== 'invalid') {
        const colName = getTableColumnName(
          columnNames,
          columnSelectFunctions,
          colId,
          opStore
        );
        metricNodes[colName] = selectFn;
      }
    }
  }
  return opMap({
    arr: rowsNode as any,
    mapFn: constFunction(
      {row: exampleRowNode.type, index: 'number'},
      ({row, index}) =>
        opMerge({
          lhs:
            Object.keys(groupByColumns).length > 0
              ? opGroupGroupKey({
                  obj: row,
                })
              : opDict({} as any),
          rhs: opDict({...metricNodes, _index: index} as any),
        } as any)
    ),
  } as any);
}

export function getResultTableNode(
  rowsNode: Node,
  columnSelectFunctions: ColumnSelectFunctions,
  columnNames: {[colId: string]: string},
  groupByColumns: GroupByColumns,
  order: ColumnOrder,
  opStore: OpStore
) {
  if (!Object.values(columnSelectFunctions).some(n => n.type !== 'invalid')) {
    return constNodeUnsafe(
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

  return resultTableNodeRegularStyle(
    order,
    groupByColumns,
    columnSelectFunctions,
    columnNames,
    rowsNode,
    exampleRowNode,
    opStore
  );
}

export function tableGetResultTableNode(
  tableState: TableState,
  inputNode: Node,
  weave: WeaveInterface
) {
  const exampleInputFrame = getRowFrame(inputNode);

  const rowsNode = getRowsNode(
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    inputNode,
    weave
  );
  const resultNode = getResultTableNode(
    rowsNode,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.groupBy,
    tableState.order,
    weave.client.opStore
  );

  return {exampleInputFrame, rowsNode, resultNode};
}
export function tableGetColumnVars(
  tableState: TableState,
  inputNode: Node,
  weave: WeaveInterface
) {
  const rowsNode = getRowsNode(
    tableState.preFilterFunction,
    tableState.groupBy,
    tableState.columnSelectFunctions,
    tableState.columnNames,
    tableState.order,
    tableState.sort,
    inputNode,
    weave
  );
  return {row: getExampleRow(rowsNode)};
}

// Return the type of resultNode as returned by tableGetResultTableNode above.
export const getTableColType = (
  tableConfig: TableState,
  colId: string
): Type => {
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
  inputNode: Node,
  weave: WeaveInterface
) {
  const {resultNode} = tableGetResultTableNode(tableState, inputNode, weave);

  const metricNodes: {[key: string]: Node} = {};
  for (const colId of tableState.groupBy.concat(
    tableState.order.filter(cid => !tableState.groupBy.includes(cid))
  )) {
    const selectFn = tableState.columnSelectFunctions[colId];
    if (selectFn.type !== 'invalid') {
      const colName = getTableColumnName(
        tableState.columnNames,
        tableState.columnSelectFunctions,
        colId,
        weave.client.opStore
      );
      metricNodes[colName] = opPick({
        obj: varNode('any', 'row'),
        key: constString(colName),
      });
    }
  }
  const finalResult = opMap({
    arr: resultNode,
    mapFn: constFunction({row: getExampleRow(resultNode).type}, ({row}) =>
      opArray(metricNodes as any)
    ) as any,
  });
  return finalResult;
}

// OK I wrote this to make the confusion matrix with embedded plot
// nice....
export async function getColumnDomainRanges(
  weave: WeaveInterface,
  ts: TableState,
  inputNode: Node,
  stack: Stack
) {
  // TODO: Make this function do the right thing when we don't
  // already have a frame.domain!
  // let domainNode = inputNode;
  // let domainVar = varNode(inputNode.type, 'input');
  // let domainFrame: Frame = {
  //   ...frame,
  //   input: inputNode,
  // };
  const resolvedDomain = resolveVar(stack, 'domain');
  if (resolvedDomain == null) {
    return {
      rangeColFns: {},
      executableRangesNode: voidNode(),
    };
  }
  const domainNode = resolvedDomain.closure.value;
  const domainStack = resolvedDomain.closure.stack;
  const domainVar = varNode(inputNode.type, 'domain');
  const domainColSelFnPromises = _.map(
    ts.columnSelectFunctions,
    (selFn, colId) => {
      if (selFn.nodeType === 'void') {
        return Promise.resolve(voidNode());
      }
      const appliedSelFn = opFlatten({
        arr: opMap({
          arr: domainVar,
          mapFn: constFunction(
            {row: getExampleRow(domainNode).type as any},
            ({row}) => {
              const siblingRows = getRowsNode(
                ts.preFilterFunction,
                ts.groupBy,
                ts.columnSelectFunctions,
                ts.columnNames,
                ts.order,
                ts.sort,
                row,
                weave
              );
              return opMap({
                arr: siblingRows,
                /* tslint:disable-next-line */
                mapFn: constFunction({row: siblingRows.type}, ({row}) =>
                  ts.groupBy.includes(colId)
                    ? opPick({
                        obj: opGroupGroupKey({obj: row}),
                        key: constString(
                          escapeDots(
                            getTableColumnName(
                              ts.columnNames,
                              ts.columnSelectFunctions,
                              colId,
                              weave.client.opStore
                            )
                          )
                        ),
                      })
                    : weave.callFunction(selFn, {row})
                ) as any,
              });
            }
          ),
        }) as any,
      });
      return refineNode(weave.client, appliedSelFn, domainStack);
    }
  );
  const domainColSelFns = await Promise.all(
    domainColSelFnPromises as Array<Promise<Node>>
  );
  const colIds = _.keys(ts.columnSelectFunctions);
  const rangeColFns: {[colId: string]: Node} = {};
  for (let i = 0; i < colIds.length; i++) {
    const colId = colIds[i];
    const domainColSelFn = domainColSelFns[i];
    const colSelType = ts.columnSelectFunctions[colId].type;
    if (isAssignableTo(colSelType, maybe('number'))) {
      rangeColFns[colId] = opDict({
        start: opNumbersMin({numbers: domainColSelFn as any}),
        end: opNumbersMax({numbers: domainColSelFn as any}),
      } as any);
    } else if (isAssignableTo(colSelType, maybe('string'))) {
      rangeColFns[colId] = opUnique({arr: domainColSelFn as any});
    }
  }

  const executableRangesNode = opDict(
    _.mapValues(rangeColFns, rangeColFn =>
      dereferenceAllVars(rangeColFn, domainStack)
    ) as any
  );

  return {rangeColFns, executableRangesNode};
}

export function getCellValueNode(
  weave: WeaveInterface,
  rowNode: Node,
  selectFunction: NodeOrVoidNode
) {
  if (selectFunction.nodeType === 'void') {
    return selectFunction;
  }
  return weave.callFunction(selectFunction, {row: rowNode});
}

export function addColumnToTable(
  table: TableState,
  selectFn: NodeOrVoidNode<Type>,
  customId?: string
): {table: TableState; columnId: string} {
  table = appendEmptyColumn(table, undefined, customId);
  const columnId = table.order[table.order.length - 1];
  table = updateColumnSelect(table, columnId, selectFn);

  return {table, columnId};
}

export type AddColumnEntries = Array<{
  selectFn: NodeOrVoidNode;
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
  selectFn: NodeOrVoidNode<Type>,
  panelDef?: {panelID: string; panelConfig: any},
  index?: number
): TableState {
  table = appendEmptyColumn(table, index);
  const columnId = table.order[table.order.length - 1];
  table = updateColumnSelect(table, columnId, selectFn);
  table = updateColumnName(table, columnId, name);
  if (panelDef != null) {
    table = updateColumnPanelId(table, columnId, panelDef.panelID);
    table = updateColumnPanelConfig(table, columnId, panelDef.panelConfig);
  }
  return table;
}

// TableEditor compatibility
// TODO: consolidate these w/ existing functions in this module

export const COLUMN_LIMIT = 100;

export interface ColumnEntry {
  name: string;

  // Only visible columns have an ID
  id?: string;

  selectFn?: NodeOrVoidNode;
}

function addColumnToDraft(
  draft: TableState,
  key: string,
  selectFn: NodeOrVoidNode
) {
  const colId = newColumnId(draft);
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

export const columnIdForColumnName = (table: TableState, colName: string) => {
  const colEntry = Object.entries(table.columnNames).find(
    ([k, v], i) => v === colName
  );
  if (colEntry != null) {
    return colEntry[0];
  }
  return null;
};
