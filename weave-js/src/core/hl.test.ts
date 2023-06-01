import {someNodes} from './hl';
import {defaultLanguageBinding} from './language';
import {
  constBoolean,
  constFunction,
  constNumber,
  constString,
  listObjectType,
} from './model';
import {
  opArtifactVersionFile,
  opFileTable,
  opJoin,
  opNumberEqual,
  opPick,
  opRootArtifactVersion,
  opTableRows,
} from './ops';

function getJoinedTable() {
  const artifactVersion = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('dsviz_demo'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('train_results:v3'),
  });
  const file = opArtifactVersionFile({
    artifactVersion,
    path: constString('train_iou_score_table.table.json'),
  });
  const table = opFileTable({
    file: file as any,
  });
  const tableRows = opTableRows({
    table: table as any,
  });

  return opJoin({
    arr1: tableRows as any,
    arr2: tableRows as any,
    join1Fn: constFunction({row: listObjectType(tableRows.type)}, ({row}) =>
      opPick({obj: row, key: constString('a')})
    ) as any,
    join2Fn: constFunction({row: listObjectType(tableRows.type)}, ({row}) =>
      opPick({obj: row, key: constString('a')})
    ) as any,
    alias1: constString('arr1'),
    alias2: constString('arr2'),
    leftOuter: constBoolean(true),
    rightOuter: constBoolean(true),
  });
}

describe('hl', () => {
  it('joined table string', () => {
    expect(defaultLanguageBinding.printGraph(getJoinedTable())).toEqual(
      `artifactVersion(
    "shawn",
    "dsviz_demo",
    "dataset",
    "train_results:v3")
  .file("train_iou_score_table.table.json")
  .table
  .rows
  .join(artifactVersion(
    "shawn",
    "dsviz_demo",
    "dataset",
    "train_results:v3")
  .file("train_iou_score_table.table.json")
  .table
  .rows, (row) => row["a"], (row) => row["a"], "arr1", "arr2", true, true)`
    );
  });
});

describe('someNodes', () => {
  it('finds input vars', () => {
    expect(
      someNodes(
        {
          nodeType: 'output',
          type: 'number',
          fromOp: {
            name: 'file-size',
            inputs: {
              file: {
                nodeType: 'var',
                type: {
                  type: 'file',
                  extension: 'json',
                  wbObjectType: {type: 'table', columnTypes: {}},
                },
                varName: 'row',
              },
            },
          },
        },
        n => n.nodeType === 'var'
      )
    ).toBeTruthy();
  });

  it('does not ever return true on false predicate', () => {
    expect(
      someNodes(
        {
          nodeType: 'output',
          type: 'number',
          fromOp: {
            name: 'file-size',
            inputs: {
              file: {
                nodeType: 'var',
                type: {
                  type: 'file',
                  extension: 'json',
                  wbObjectType: {type: 'table', columnTypes: {}},
                },
                varName: 'row',
              },
            },
          },
        },
        n => n.nodeType === 'const'
      )
    ).toBeFalsy();
  });

  it('ignores input vars in function body when excludeFnBodies is true', () => {
    expect(
      someNodes(
        {
          nodeType: 'output',
          type: 'number',
          fromOp: {
            name: 'filter',
            inputs: {
              arr: {
                nodeType: 'const',
                type: 'number',
                val: [1, 2, 3],
              },
              filterFn: constFunction({row: 'number'}, ({row}) =>
                opNumberEqual({lhs: row, rhs: constNumber(1)})
              ),
            },
          },
        },
        n => n.nodeType === 'var',
        true
      )
    ).toBeFalsy();
  });
});
