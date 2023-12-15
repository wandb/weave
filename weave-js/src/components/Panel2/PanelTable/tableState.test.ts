import * as _ from 'lodash';

import {
  constNodeUnsafe,
  constNumber,
  constString,
  list,
  maybe,
  Node,
  nullableTaggableValue,
  opCount,
  opNumberGreaterEqual,
  opNumbersSum,
  opPick,
  opProjectRuns,
  opRootProject,
  opRunSummary,
  tableRowValue,
  typedDict,
  union,
  varNode,
  withGroupTag,
} from '../../../core';
import * as Table from './tableState';
import {
  getTableCellTypes,
  getTableCellValues,
  getTableRowsNode,
  initTable,
  testWeave,
} from './tableState.test.fixtures';

const extractPickKeyFromNode = (op: Node) => {
  if (op.nodeType === 'output') {
    if (op.fromOp.name === 'pick') {
      const keyNode = op.fromOp.inputs.key;
      if (keyNode.nodeType === 'const') {
        return keyNode.val;
      }
    }
  }
  return null;
};

describe('table', () => {
  it('can get cell values', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();

    // Initialize a table and add a new column
    let ts = Table.emptyTable();
    ts = Table.appendColumn(ts, tableRows, weave);
    let values = await getTableCellValues(ts, tableRows);
    // The function is identity by default
    expect(values).toEqual([
      [{a: 14, b: -1, x: 'cat'}],
      [{a: 14, b: -1, x: 'cat'}],
      [{a: 14, b: -2, x: 'dog'}],
      [{a: 1, b: 2, x: 'dog'}],
      [{a: 9, b: 2, x: 'dog'}],
    ]);

    // Select column a from underlying table
    const selFn = opPick({
      obj: varNode('any', 'row') as any,
      key: constString('a'),
    });
    ts = Table.updateColumnSelect(ts, ts.order[0], selFn);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([[14], [14], [14], [1], [9]]);

    // Appending a new column results in more undefined values
    ts = Table.appendColumn(ts, tableRows, weave);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [14, {a: 14, b: -1, x: 'cat'}],
      [14, {a: 14, b: -1, x: 'cat'}],
      [14, {a: 14, b: -2, x: 'dog'}],
      [1, {a: 1, b: 2, x: 'dog'}],
      [9, {a: 9, b: 2, x: 'dog'}],
    ]);

    // Select column x for second column
    const selFn2 = opPick({
      obj: varNode('any', 'row') as any,
      key: constString('x'),
    });
    ts = Table.updateColumnSelect(ts, ts.order[1], selFn2);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [14, 'cat'],
      [14, 'cat'],
      [14, 'dog'],
      [1, 'dog'],
      [9, 'dog'],
    ]);
  });

  it('group by', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();
    let ts = await initTable(weave, tableRows, ['a', 'x']);
    let values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [14, 'cat'],
      [14, 'cat'],
      [14, 'dog'],
      [1, 'dog'],
      [9, 'dog'],
    ]);
    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      ['cat', [14, 14]],
      ['dog', [14, 1, 9]],
    ]);

    ts = await Table.disableGroupByCol(ts, ts.groupBy[0], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [14, 'cat'],
      [14, 'cat'],
      [14, 'dog'],
      [1, 'dog'],
      [9, 'dog'],
    ]);
  });

  // This is no longer true, we rely on useTableStateWithRefinedExpressions to
  // fix the types up at render time.
  it.skip('group by changes select types', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();
    let ts = await initTable(weave, tableRows, ['a', 'x']);
    expect(getTableCellTypes(ts)).toEqual([
      tableRowValue('number'),
      tableRowValue('string'),
    ]);

    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    expect(getTableCellTypes(ts)).toEqual([
      tableRowValue('string'),
      withGroupTag(
        list(tableRowValue('number')),
        typedDict({
          x: tableRowValue('string'),
        })
      ),
    ]);

    ts = await Table.disableGroupByCol(ts, ts.groupBy[0], tableRows, weave, []);
    expect(getTableCellTypes(ts)).toEqual([
      tableRowValue('number'),
      tableRowValue('string'),
    ]);
  });

  it('group by boolean select', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();
    let ts = await initTable(weave, tableRows, ['a', 'x']);
    ts = Table.updateColumnSelect(
      ts,
      ts.order[0],
      opNumberGreaterEqual({
        lhs: opPick({
          obj: varNode('any', 'row') as any,
          key: constString('a'),
        }) as any,
        rhs: constNumber(5),
      })
    );
    let values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [true, 'cat'],
      [true, 'cat'],
      [true, 'dog'],
      [false, 'dog'],
      [true, 'dog'],
    ]);
    ts = await Table.enableGroupByCol(ts, ts.order[0], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [false, ['dog']],
      [true, ['cat', 'cat', 'dog', 'dog']],
    ]);
  });

  it('group by variable', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();
    const tableRowType = Table.getExampleRow(tableRows);
    let ts = await initTable(weave, tableRows, ['a', 'x']);
    const lookupType = typedDict({cat: 'string', dog: 'string'});
    ts = Table.updateColumnSelect(
      ts,
      ts.order[0],
      opPick({
        obj: varNode(lookupType, 'lookup') as any,
        key: opPick({
          obj: varNode(tableRowType.type, 'row'),
          key: constString('x'),
        }),
      }) as any
    );
    const frame = {lookup: constNodeUnsafe(lookupType, {cat: 4, dog: 6})};
    let values = await getTableCellValues(ts, tableRows, frame);
    expect(values).toEqual([
      [4, 'cat'],
      [4, 'cat'],
      [6, 'dog'],
      [6, 'dog'],
      [6, 'dog'],
    ]);
    ts = await Table.enableGroupByCol(ts, ts.order[0], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows, frame);
    expect(values).toEqual([
      [4, ['cat', 'cat']],
      [6, ['dog', 'dog', 'dog']],
    ]);
  });
  it('group by multiple columns', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode('groupby_examples.table.json');
    let ts = await initTable(weave, tableRows, ['id', 'species', 'napSpot']);
    let values = await getTableCellValues(ts, tableRows);
    // precondition
    expect(values).toEqual([
      [1, 'dog', 'couch'],
      [7, 'narwhal', 'under the sea'],
      [2, 'dog', 'bed'],
      [3, 'dog', 'bed'],
      [4, 'cat', 'couch'],
      [5, 'cat', 'windowsill'],
      [6, 'cat', 'couch'],
    ]);
    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      ['cat', [4, 5, 6], ['couch', 'windowsill', 'couch']],
      ['dog', [1, 2, 3], ['couch', 'bed', 'bed']],
      ['narwhal', [7], ['under the sea']],
    ]);
    ts = await Table.enableGroupByCol(ts, ts.order[2], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    // note that we want to ensure that the first grouped columns stay together
    expect(values).toEqual([
      ['cat', 'couch', [4, 6]],
      ['cat', 'windowsill', [5]],
      ['dog', 'couch', [1]],
      ['dog', 'bed', [2, 3]],
      ['narwhal', 'under the sea', [7]],
    ]);
    ts = await Table.disableGroupByCol(ts, ts.groupBy[1], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      ['cat', [4, 5, 6], ['couch', 'windowsill', 'couch']],
      ['dog', [1, 2, 3], ['couch', 'bed', 'bed']],
      ['narwhal', [7], ['under the sea']],
    ]);

    ts = await Table.disableGroupByCol(ts, ts.groupBy[0], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [1, 'dog', 'couch'],
      [7, 'narwhal', 'under the sea'],
      [2, 'dog', 'bed'],
      [3, 'dog', 'bed'],
      [4, 'cat', 'couch'],
      [5, 'cat', 'windowsill'],
      [6, 'cat', 'couch'],
    ]);
  });
  it('group by multiple columns - remove in order added', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode('groupby_examples.table.json');
    let ts = await initTable(weave, tableRows, ['id', 'species', 'napSpot']);
    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    let values = await getTableCellValues(ts, tableRows);
    ts = await Table.enableGroupByCol(ts, ts.order[2], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    // precondition
    expect(values).toEqual([
      ['cat', 'couch', [4, 6]],
      ['cat', 'windowsill', [5]],
      ['dog', 'couch', [1]],
      ['dog', 'bed', [2, 3]],
      ['narwhal', 'under the sea', [7]],
    ]);
    ts = await Table.disableGroupByCol(ts, ts.groupBy[1], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      ['cat', [4, 5, 6], ['couch', 'windowsill', 'couch']],
      ['dog', [1, 2, 3], ['couch', 'bed', 'bed']],
      ['narwhal', [7], ['under the sea']],
    ]);

    ts = await Table.disableGroupByCol(ts, ts.groupBy[0], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      [1, 'dog', 'couch'],
      [7, 'narwhal', 'under the sea'],
      [2, 'dog', 'bed'],
      [3, 'dog', 'bed'],
      [4, 'cat', 'couch'],
      [5, 'cat', 'windowsill'],
      [6, 'cat', 'couch'],
    ]);
  });
  it('group by multiple columns - sort by first grouped column', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode('groupby_examples.table.json');
    let ts = await initTable(weave, tableRows, ['id', 'species', 'napSpot']);
    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    let values = await getTableCellValues(ts, tableRows);
    ts = await Table.enableGroupByCol(ts, ts.order[2], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    // precondition
    expect(values).toEqual([
      ['cat', 'couch', [4, 6]],
      ['cat', 'windowsill', [5]],
      ['dog', 'couch', [1]],
      ['dog', 'bed', [2, 3]],
      ['narwhal', 'under the sea', [7]],
    ]);
    ts = await Table.enableSortByCol(ts, ts.order[1], true);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      ['cat', 'couch', [4, 6]],
      ['cat', 'windowsill', [5]],
      ['dog', 'couch', [1]],
      ['dog', 'bed', [2, 3]],
      ['narwhal', 'under the sea', [7]],
    ]);
  });

  it('group by multiple columns - sort by second grouped column', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode('groupby_examples.table.json');
    let ts = await initTable(weave, tableRows, ['id', 'species', 'napSpot']);
    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    let values = await getTableCellValues(ts, tableRows);
    ts = await Table.enableGroupByCol(ts, ts.order[2], tableRows, weave, []);
    values = await getTableCellValues(ts, tableRows);
    // precondition
    expect(values).toEqual([
      ['cat', 'couch', [4, 6]],
      ['cat', 'windowsill', [5]],
      ['dog', 'couch', [1]],
      ['dog', 'bed', [2, 3]],
      ['narwhal', 'under the sea', [7]],
    ]);
    ts = await Table.enableSortByCol(ts, ts.order[2], true);
    values = await getTableCellValues(ts, tableRows);
    expect(values).toEqual([
      ['cat', 'couch', [4, 6]],
      ['cat', 'windowsill', [5]],
      ['dog', 'bed', [2, 3]],
      ['dog', 'couch', [1]],
      ['narwhal', 'under the sea', [7]],
    ]);
  });
  it('group by - sort by non-grouped aggregated column works', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode('groupby_examples.table.json');
    let ts = await initTable(weave, tableRows, ['id', 'species', 'napSpot']);
    // this is the equivalent of user entering 'row.count'
    const rowCountSelectFn = opCount({
      arr: varNode({type: 'list', objectType: 'run'}, 'row') as any,
    });
    const {table} = await Table.addColumnToTable(ts, rowCountSelectFn);
    ts = table;
    ts = await Table.enableGroupByCol(ts, ts.order[1], tableRows, weave, []);
    const values = await getTableCellValues(ts, tableRows);
    // precondition
    expect(values).toEqual([
      ['cat', [4, 5, 6], ['couch', 'windowsill', 'couch'], 3],
      ['dog', [1, 2, 3], ['couch', 'bed', 'bed'], 3],
      ['narwhal', [7], ['under the sea'], 1],
    ]);

    // we disable sorting on the group by column here to make testing easier
    ts = await Table.disableSortByCol(ts, ts.order[1]);
    ts = await Table.enableSortByCol(ts, ts.order[3], true);
    const actual = await getTableCellValues(ts, tableRows);
    expect(actual).toEqual([
      ['narwhal', [7], ['under the sea'], 1],
      ['dog', [1, 2, 3], ['couch', 'bed', 'bed'], 3],
      ['cat', [4, 5, 6], ['couch', 'windowsill', 'couch'], 3],
    ]);
  });
});

describe('initial columns', () => {
  it('single level works', async () => {
    const objType = typedDict({a: 'number', b: 'number'});
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual(['a', 'b']);
  });
  it.skip('tails are merged for matching keys in subobjects', async () => {
    const objType = typedDict({
      a: typedDict({x: 'number', y1: 'number'}),
      b: typedDict({x: 'number', y2: 'number'}),
    });
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual(['*.x', 'a.y1', 'b.y2']);
  });
  it.skip('different types are not merged', async () => {
    const objType = typedDict({
      a: typedDict({x: 'number', y1: 'number'}),
      b: typedDict({x: 'string', y2: 'number'}),
    });
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual(['b.x', 'a.x', 'a.y1', 'b.y2']);
  });
  it.skip('three-level tail merge', async () => {
    const objType = typedDict({
      a: typedDict({
        x: 'number',
        y1: typedDict({j: 'number', k1: 'number'}),
      }),
      b: typedDict({
        x: 'number',
        y2: typedDict({j: 'number', k2: 'number'}),
      }),
    });
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual(['*.x', '*.*.j', 'a.y1.k1', 'b.y2.k2']);
  });
  it.skip('maybe types are merged', async () => {
    const objType = typedDict({
      a: typedDict({
        x: maybe('number'),
        y: 'string',
      }),
      b: typedDict({
        x: 'number',
        y: maybe('string'),
      }),
    });
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual(['*.y', '*.x']);
  });
  it.skip('media types are not grouped', async () => {
    const objType = typedDict({
      a: typedDict({x: {type: 'image-file'}, y: 'number'}),
      b: typedDict({x: {type: 'image-file'}, y: 'number'}),
    });
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual(['a.x', 'b.x', '*.y']);
  });
  it.skip('sort order: id, media, string, other', async () => {
    const objType = typedDict({
      a: typedDict({
        m: 'number',
        y: maybe({type: 'video-file'}),
        n1: 'number',
        x: {type: 'image-file'},
        id: 'string',
        astring: union(['string', 'none']),
      }),
      b: typedDict({
        m: 'number',
        y: {type: 'video-file'},
        n2: 'number',
        x: {type: 'image-file'},
        UUID: 'string',
      }),
    });
    expect(
      Table.autoTableColumnExpressions(objType, objType).map(
        extractPickKeyFromNode
      )
    ).toEqual([
      'a.id',
      'b.UUID',
      'a.y',
      'b.y',
      'a.x',
      'b.x',
      'a.astring',
      '*.m',
      'a.n1',
      'b.n2',
    ]);
  });

  it('tableGetResultTableNode works', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();

    // Initialize a table and add a new column
    let ts = Table.emptyTable();
    ts = Table.appendColumn(ts, tableRows, weave);
    const selFn = opPick({
      obj: varNode('any', 'row') as any,
      key: constString('a'),
    });
    ts = Table.updateColumnSelect(ts, ts.order[0], selFn);
    const {resultNode} = Table.tableGetResultTableNode(ts, tableRows, weave);
    expect(await weave.client.query(resultNode as any)).toEqual([
      {_index: 0, a: 14},
      {_index: 1, a: 14},
      {_index: 2, a: 14},
      {_index: 3, a: 1},
      {_index: 4, a: 9},
    ]);
  });
});

const TABLE = [
  {
    a: 1,
    b: 2,
    arr: [5, 4],
    arr_obj: [
      {
        x: 1,
        y: 2,
        z: 3,
      },
    ],
  },
  {
    a: 19,
    b: 2,
    arr: [5, 9],
    arr_obj: [
      {
        x: 1,
        y: 5,
        z: 3,
      },
    ],
  },
  {
    a: 1,
    b: 2,
    arr: [7, 12],
    arr_obj: [
      {
        x: 1,
        y: 2,
        z: 2,
      },
    ],
  },
  {
    a: 4,
    b: 2,
    arr: [100, 101],
    arr_obj: [
      {
        x: 1,
        y: 2,
        z: 3,
      },
      {
        x: 99,
        y: 98,
        z: 97,
      },
    ],
  },
];
const TABLE_ROW_TYPE = typedDict({
  a: 'number',
  b: 'number',
  arr: list('number'),
  arr_obj: list(typedDict({x: 'number', y: 'number', z: 'number'})),
});
const TABLE_NODE = constNodeUnsafe(list(TABLE_ROW_TYPE), TABLE);

describe('standard v. unnest style queries', () => {
  it('simple select', async () => {
    const weave = testWeave();
    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      xColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('a'),
      }) as any
    );
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([[1], [19], [1], [4]]);
  });

  it('simple select 2', async () => {
    const weave = testWeave();
    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      xColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('a'),
      }) as any
    );
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      yColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr'),
      }) as any
    );
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [1, [5, 4]],
      [19, [5, 9]],
      [1, [7, 12]],
      [4, [100, 101]],
    ]);
  });

  it('simple group by', async () => {
    const weave = testWeave();
    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      xColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('a'),
      }) as any
    );
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      yColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr'),
      }) as any
    );
    visTable = {...visTable, groupBy: [xColId]};
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [
        1,
        [
          [5, 4],
          [7, 12],
        ],
      ],
      [19, [[5, 9]]],
      [4, [[100, 101]]],
    ]);
  });

  it.skip('array group by', async () => {
    const weave = testWeave();
    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      xColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('a'),
      }) as any
    );
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      yColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr'),
      }) as any
    );
    visTable = {...visTable, groupBy: [yColId]};
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [5, [1, 19]],
      [4, [1]],
      [9, [19]],
      [7, [1]],
      [12, [1]],
      [100, [4]],
      [101, [4]],
    ]);
  });

  it.skip('array obj group by', async () => {
    const weave = testWeave();
    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      xColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('a'),
      }) as any
    );
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      yColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr_obj'),
      }) as any
    );
    visTable = {...visTable, groupBy: [yColId]};
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [{x: 1, y: 2, z: 3}, [1, 4]],
      [{x: 1, y: 5, z: 3}, [19]],
      [{x: 1, y: 2, z: 2}, [1]],
      [{x: 99, y: 98, z: 97}, [4]],
    ]);
  });

  it.skip('array obj subkey group by', async () => {
    const weave = testWeave();

    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    visTable = Table.updateColumnSelect(
      visTable,
      xColId,
      opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('a'),
      }) as any
    );
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    const selFn = opPick({
      obj: opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr_obj'),
      }) as any,
      key: constString('x'),
    }) as any;
    const selFnRefined = await weave.refineNode(selFn, []);
    visTable = Table.updateColumnSelect(visTable, yColId, selFnRefined);
    visTable = {...visTable, groupBy: [yColId]};
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [1, [1, 19, 1, 4]],
      [99, [4]],
    ]);
  });

  it.skip('array obj subkey group by select array obj', async () => {
    const weave = testWeave();

    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    const selFn1 = opPick({
      obj: opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr_obj'),
      }) as any,
      key: constString('y'),
    }) as any;
    const selFn1Refined = await weave.refineNode(selFn1, []);
    visTable = Table.updateColumnSelect(visTable, xColId, selFn1Refined);
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    const selFn = opPick({
      obj: opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr_obj'),
      }) as any,
      key: constString('x'),
    }) as any;
    const selFnRefined = await weave.refineNode(selFn, []);
    visTable = Table.updateColumnSelect(visTable, yColId, selFnRefined);
    visTable = {...visTable, groupBy: [yColId]};
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [1, [2, 5, 2, 2]],
      [99, [98]],
    ]);
  });

  it.skip('array obj subkey group by select array obj sum', async () => {
    const weave = testWeave();

    let visTable = Table.emptyTable();
    visTable = Table.appendEmptyColumn(visTable);
    const xColId = visTable.order[visTable.order.length - 1];
    const selFn1 = opNumbersSum({
      numbers: opPick({
        obj: opPick({
          obj: varNode(TABLE_ROW_TYPE, 'row') as any,
          key: constString('arr_obj'),
        }) as any,
        key: constString('y'),
      }) as any,
    });
    const selFn1Refined = await weave.refineNode(selFn1, []);
    visTable = Table.updateColumnSelect(visTable, xColId, selFn1Refined);
    visTable = Table.appendEmptyColumn(visTable);
    const yColId = visTable.order[visTable.order.length - 1];
    const selFn = opPick({
      obj: opPick({
        obj: varNode(TABLE_ROW_TYPE, 'row') as any,
        key: constString('arr_obj'),
      }) as any,
      key: constString('x'),
    }) as any;
    const selFnRefined = await weave.refineNode(selFn, []);
    visTable = Table.updateColumnSelect(visTable, yColId, selFnRefined);
    visTable = {...visTable, groupBy: [yColId]};
    visTable = await Table.refreshSelectFunctions(
      visTable,
      TABLE_NODE,
      weave,
      []
    );

    const result = await getTableCellValues(visTable, TABLE_NODE);
    expect(result).toEqual([
      [1, 11],
      [99, 98],
    ]);
  });
});

describe.skip('column domains', () => {
  it('works when no outer domain present', async () => {
    const weave = testWeave();
    const tableRows = await getTableRowsNode();
    const tableRowsObjectType = (tableRows.type as any).objectType;

    // Initialize a table and add a new column
    let ts = Table.emptyTable();

    ts = Table.appendColumn(ts, tableRows, weave);
    let selFn = opPick({
      obj: varNode(tableRowsObjectType, 'row') as any,
      key: constString('a'),
    });
    ts = Table.updateColumnSelect(ts, ts.order[0], selFn);

    ts = Table.appendColumn(ts, tableRows, weave);
    selFn = opPick({
      obj: varNode(tableRowsObjectType, 'row') as any,
      key: constString('x'),
    });
    ts = Table.updateColumnSelect(ts, ts.order[1], selFn);
    const ranges = await Table.getColumnDomainRanges(weave, ts, tableRows, []);
    if (ranges.executableRangesNode.nodeType === 'void') {
      throw new Error('invalid');
    }
    const rangeResults = await weave.client.query(ranges.executableRangesNode);

    // For numeric column, we expect to get a numeric range
    const rangeColFn0 = _.values(ranges.rangeColFns)[0];
    expect(weave.expToString(rangeColFn0).replace(/[\n ]/g, '')).toEqual(
      '({start:input.flatten.map((row)=>row["a"]).min,end:input.flatten.map((row)=>row["a"]).max,})'
    );
    expect(rangeResults[ts.order[0]]).toEqual({start: 1, end: 14});

    // For a string column, we expect to get a list of unique items
    const rangeColFn1 = _.values(ranges.rangeColFns)[1];
    expect(weave.expToString(rangeColFn1).replace(/[\n ]/g, '')).toEqual(
      'input.flatten.map((row)=>row["x"]).unique'
    );
    expect(rangeResults[ts.order[1]]).toEqual(['cat', 'dog']);
  });
});

describe('runs table', () => {
  it('summary column type', async () => {
    const weave = testWeave();
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const fasionSweepRuns = opProjectRuns({
      project: opRootProject({entityName, projectName}),
    });
    let table = await initTable(weave, fasionSweepRuns);
    ({table} = Table.addColumnToTable(
      table,
      opRunSummary({run: varNode('run', 'row')})
    ));
    table = await Table.refreshSelectFunctions(
      table,
      fasionSweepRuns,
      weave,
      []
    );
    expect(
      nullableTaggableValue(table.columnSelectFunctions[table.order[1]].type)
    ).toEqual({
      members: [
        {propertyTypes: {x: 'number', y: 'number'}, type: 'typedDict'},
        {
          propertyTypes: {
            table: {
              extension: 'json',
              type: 'file',
              wbObjectType: {columnTypes: {}, type: 'table'},
            },
            joinedTable: {
              extension: 'json',
              type: 'file',
              wbObjectType: {
                columnTypes: {},
                type: 'joined-table',
              },
            },
            partitionedTable: {
              extension: 'json',
              type: 'file',
              wbObjectType: {
                columnTypes: {},
                type: 'partitioned-table',
              },
            },
            x: 'number',
            y: 'number',
            z: typedDict({a: 'string', b: 'number'}),
          },
          type: 'typedDict',
        },
      ],
      type: 'union',
    });
  });
});
