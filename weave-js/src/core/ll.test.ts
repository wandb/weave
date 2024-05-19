/* tslint:disable */

import {mapNodes} from './callers';
import * as HL from './hl';
import type {Node} from './model';
import {
  constBoolean,
  constFunction,
  constNode,
  constNodeUnsafe,
  constNumber,
  constString,
  file,
  list,
  listWithLength,
  maybe,
  tableRowValueMaybeFile,
  taggedValue,
  typedDict,
  withFileTag,
} from './model';
import {
  applyOpToOneOrMany,
  opArray,
  opArtifactVersionFile,
  opArtifactVersionSize,
  opCount,
  opDropNa,
  opFileJoinedTable,
  opFilePartitionedTable,
  opFileTable,
  opGetTag,
  opIndex,
  opJoinedTableRows,
  opMap,
  opNumberAdd,
  opNumbersAvg,
  opNumbersSum,
  opNumberSub,
  opOrgMembers,
  opPartitionedTableRows,
  opPick,
  opProjectCreatedAt,
  opProjectName,
  opProjectRuns,
  opRootArtifactVersion,
  opRootOrg,
  opRootProject,
  opRunSummary,
  opTableRows,
  opUserId,
  opUserRuns,
  opUserUsername,
  spread,
} from './ops';
import {StaticOpStore} from './opStore';
import {testClient} from './testUtil';

function getDSVizJoinedTable() {
  const artifactVersion = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('dsviz_demo'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('train_results:v2'),
  });
  const artifactFile = opArtifactVersionFile({
    artifactVersion,
    path: constString('train-results.joined-table.json'),
  });
  const joinedTable = opFileJoinedTable({
    file: artifactFile as any,
  });
  return joinedTable;
}

function getDSVizPartitionedTable() {
  const artifactVersion = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('dsviz_demo'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('train_results:v2'),
  });
  const artifactFile = opArtifactVersionFile({
    artifactVersion,
    path: constString('part_table.partitioned-table.json'),
  });
  const partitionedTable = opFilePartitionedTable({
    file: artifactFile as any,
  });
  return partitionedTable;
}

describe('ll', () => {
  it('builds', () => {
    const graph = opRootProject({
      entityName: constString('shawn'),
      projectName: constString('fasionSweep'),
    });
    expect(graph).toEqual({
      fromOp: {
        inputs: {
          entityName: {nodeType: 'const', type: 'string', val: 'shawn'},
          projectName: {nodeType: 'const', type: 'string', val: 'fasionSweep'},
        },
        name: 'root-project',
      },
      nodeType: 'output',
      type: {
        tag: {
          propertyTypes: {entityName: 'string', projectName: 'string'},
          type: 'typedDict',
        },
        type: 'tagged',
        value: 'project',
      },
    });
  });

  it('const string', async () => {
    const client = await testClient();
    expect(client.query(constString('hello'))).resolves.toEqual('hello');
  });

  it('root artifact', async () => {
    const client = await testClient();
    const artifactVersion = opRootArtifactVersion({
      entityName: constString('shawn'),
      projectName: constString('dsviz_demo'),
      artifactTypeName: constString('dataset'),
      artifactVersionName: constString('train_results:v3'),
    });
    const artifactSize = opArtifactVersionSize({artifactVersion});
    return expect(client.query(artifactSize)).resolves.toEqual(1921);
  });

  it('artifact file table', async () => {
    const client = await testClient();
    const artifactVersion = opRootArtifactVersion({
      entityName: constString('shawn'),
      projectName: constString('dsviz_demo'),
      artifactTypeName: constString('dataset'),
      artifactVersionName: constString('train_results:v2'),
    });
    const file = opArtifactVersionFile({
      artifactVersion,
      path: constString('train_iou_score_table.table.json'),
    });
    const table = opFileTable({
      file: file as any,
    });
    expect(table.type).toEqual(
      maybe(
        withFileTag(maybe({type: 'table', columnTypes: {}}), {
          type: 'file',
          extension: 'json',
          wbObjectType: {type: 'table', columnTypes: {}},
        })
      )
    );

    expect(client.query(table)).resolves.toEqual({
      columns: ['a', 'b', 'x'],
      data: [
        [14, -1, 'cat'],
        [14, -1, 'cat'],
        [14, -2, 'dog'],
        [1, 2, 'dog'],
        [9, 2, 'dog'],
      ],
    });
    const tableRows = opTableRows({
      table: table as any,
    });
    const tableRow3 = opIndex({
      arr: tableRows as any,
      index: constNodeUnsafe('number', 3),
    }) as any;
    const tableRow3b = opPick({
      obj: tableRow3 as any,
      key: constString('b'),
    });
    return expect(client.query(tableRow3b)).resolves.toEqual(2);
  });

  it('artifact file types', async () => {
    const client = await testClient();
    const artifactVersion = opRootArtifactVersion({
      entityName: constString('shawn'),
      projectName: constString('dsviz_demo'),
      artifactTypeName: constString('dataset'),
      artifactVersionName: constString('train_results:v3'),
    });
    const artifactFile = opArtifactVersionFile({
      artifactVersion,
      path: constString('train_iou_score_table.table.json'),
    });
    const fileWithType = await HL.refineNode(client, artifactFile, []);
    expect(fileWithType.type).toEqual({
      extension: 'json',
      type: 'file',
      wbObjectType: {type: 'table', columnTypes: {}},
    });

    const artifactVersion2 = opRootArtifactVersion({
      entityName: constString('shawn'),
      projectName: constString('dsviz_demo'),
      artifactTypeName: constString('dataset'),
      artifactVersionName: constString('train_results:v2'),
    });
    const artifacts = opArray(
      spread([artifactVersion, artifactVersion2]) as any
    );
    const artifactsFiles = applyOpToOneOrMany(
      opArtifactVersionFile,
      'artifactVersion',
      artifacts,
      {
        path: constString('train_iou_score_table.table.json'),
      }
    );
    expect(artifactsFiles.type).toEqual({
      objectType: maybe({type: 'file'}),
      type: 'list',
      maxLength: 2,
      minLength: 2,
    });
    const filesWithType = await HL.refineNode(client, artifactsFiles, []);
    expect(filesWithType.type).toEqual({
      objectType: {
        type: 'file',
        extension: 'json',
        wbObjectType: {type: 'table', columnTypes: {}},
      },
      type: 'list',
      maxLength: 2,
      minLength: 2,
    });
  });

  it.skip('org', async () => {
    const client = await testClient();
    const orgName = constString('wandb');
    const org = opRootOrg({orgName});
    const members = opOrgMembers({org});
    const user = opIndex({
      arr: members as any,
      index: constNodeUnsafe('number', 0),
    }) as any;
    const userId = opUserId({user});
    expect(client.query(userId)).resolves.toEqual(0);
    const userUsername = opUserUsername({user});
    expect(client.query(userUsername)).resolves.toEqual('shawn');
    const runs = opUserRuns({user});
    const runsCount = opCount({arr: runs as any});
    return expect(client.query(runsCount)).resolves.toEqual([8, 5]);
  });

  it('math', async () => {
    const client = await testClient();
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const project = opRootProject({entityName, projectName});

    const runs = opProjectRuns({project});
    const runsCount = opCount({arr: runs as any});
    const runsSummaryX = opMap({
      arr: runs as any,
      mapFn: constFunction({row: 'run'}, ({row}) =>
        opPick({
          obj: opRunSummary({run: row}),
          key: constString('x'),
        })
      ) as any,
    });

    const avgRunsSummaryX = opNumbersAvg({numbers: runsSummaryX});

    const avgRunsSummaryXMinusRunsCount = opNumberSub({
      lhs: avgRunsSummaryX,
      rhs: runsCount as any,
    });

    return expect(client.query(avgRunsSummaryXMinusRunsCount)).resolves.toEqual(
      42.9
    );
  });

  it('nested OpMap', async () => {
    const client = await testClient();
    const inputArr = opArray({
      0: constNumber(0),
      1: constNumber(1),
      2: constNumber(2),
      3: constNumber(3),
      4: constNumber(4),
    } as any);
    const level1 = opMap({
      arr: inputArr,
      mapFn: constFunction({row: 'number'}, ({row}) =>
        opNumberAdd({
          lhs: row,
          rhs: constNumber(10),
        })
      ) as any,
    });
    const level2 = opMap({
      arr: inputArr,
      mapFn: constFunction({row: 'number'}, ({row}) =>
        opNumberAdd({
          lhs: opNumbersSum({numbers: level1 as any}),
          rhs: row,
        })
      ) as any,
    });

    return expect(client.query(level2)).resolves.toEqual([60, 61, 62, 63, 64]);
  });

  it('available Ops', () => {
    expect(
      HL.rootOps(StaticOpStore.getInstance()).map(opDef => opDef.name)
    ).toEqual(['root-project', 'range']);

    const project = opRootProject({
      entityName: constString('shawn'),
      projectName: constString('fasion-sweep'),
    });

    expect(
      HL.availableOpsForChain(project, StaticOpStore.getInstance()).map(
        opDef => opDef.name
      )
    ).toEqual([
      'isNone',
      'project-createdAt',
      'project-updatedAt',
      'project-name',
      'project-runs',
      'project-artifactType',
      'project-artifactTypes',
      'project-artifact',
      'project-artifactVersion',
    ]);
  });

  it('executeForward', async () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const project = opRootProject({entityName, projectName});

    const runs = opProjectRuns({project});
    const runsCount = opCount({arr: runs as any});
    const runsSummaryX = opMap({
      arr: runs as any,
      mapFn: constFunction({row: 'run'}, ({row}) =>
        opPick({
          obj: opRunSummary({run: row}),
          key: constString('x'),
        })
      ),
    });
    const avgRunsSummaryX = opNumbersAvg({numbers: runsSummaryX});
    const avgRunsSummaryXMinusRunsCount = opNumberSub({
      lhs: avgRunsSummaryX,
      rhs: runsCount as any,
    });

    const client = await testClient();
    const results = [
      await client.query(runsCount),
      await client.query(avgRunsSummaryXMinusRunsCount),
    ];
    return expect(results).toEqual([2, 42.9]);
  });

  it('ui sim', () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const project = opRootProject({entityName, projectName});
    const runs = opProjectRuns({project});
    const runsCount = opCount({arr: runs as any});

    return new Promise<void>(resolve => {
      testClient().then(client => {
        const obs = client.subscribe(runsCount);
        obs.subscribe(result => {
          expect(result).toEqual(2);
          resolve();
        });
      });
    });
  });

  it('successive graphql queries with diff fields', async () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const project = opRootProject({entityName, projectName});
    const projectNameQuery = opProjectName({project});

    const client = await testClient();

    const obs1 = client.subscribe(projectNameQuery);
    const prom1 = new Promise(resolve => {
      obs1.subscribe(result => {
        resolve(result);
      });
    });
    const res1 = await prom1;
    expect(res1).toEqual('fasion-sweep');

    const projectCreatedAtQuery = opProjectCreatedAt({project});
    const obs2 = client.subscribe(projectCreatedAtQuery);
    const prom2 = new Promise(resolve => {
      obs2.subscribe(result => {
        resolve(result);
      });
    });
    const res2 = await prom2;
    expect(res2).toEqual(new Date('2019-03-01T02:44:20.000Z'));
  });

  it('joined table', async () => {
    const client = await testClient();
    const joinedTable = getDSVizJoinedTable();
    const joinedTableRows = opJoinedTableRows({
      joinedTable: joinedTable as any,
      leftOuter: constBoolean(true),
      rightOuter: constBoolean(true),
    });
    const joinedNode = await HL.refineNode(client, joinedTableRows, []);
    expect(joinedNode.type).toEqual(
      list(
        taggedValue(
          typedDict({
            joinKey: 'string',
            joinObj: maybe(
              taggedValue(
                typedDict({
                  table: maybe(
                    taggedValue(
                      typedDict({
                        file: file('json', {
                          columnTypes: {},
                          type: 'table',
                        }),
                      }),
                      maybe({
                        columnTypes: {},
                        type: 'table',
                      })
                    )
                  ),
                }),
                'number'
              )
            ),
          }),
          typedDict({
            '0': maybe(
              tableRowValueMaybeFile(
                typedDict({
                  a: 'number',
                  b: 'number',
                  x: 'string',
                })
              )
            ),
            '1': maybe(
              tableRowValueMaybeFile(
                typedDict({
                  a: 'number',
                  b: 'number',
                  j: 'string',
                  x: 'string',
                })
              )
            ),
          })
        )
      )
    );
    expect(await client.query(joinedNode)).toEqual([
      {
        '0': {a: 14, b: -1, x: 'cat'},
        '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
      },
      {
        '0': {a: 14, b: -1, x: 'cat'},
        '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
      },
      {
        '0': {a: 14, b: -2, x: 'dog'},
        '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
      },
      {
        '0': {a: 1, b: 2, x: 'dog'},
        '1': {a: 1, b: 21, j: 'j2', x: 'dog'},
      },
      {
        '0': {a: 9, b: 2, x: 'dog'},
        '1': {a: 9, b: 24, j: 'j3', x: 'roar'},
      },
    ]);
  });

  it('joined table array', async () => {
    const client = await testClient();
    const joinedTable = getDSVizJoinedTable();
    const joinedTableRows = opJoinedTableRows({
      joinedTable: joinedTable as any,
      leftOuter: constBoolean(true),
      rightOuter: constBoolean(true),
    });
    const doubleJoinedTableRows = opArray({
      0: joinedTableRows as any,
      1: joinedTableRows as any,
    } as any);
    const joinedNode = await HL.refineNode(client, doubleJoinedTableRows, []);
    expect(joinedNode.type).toEqual(
      listWithLength(
        2,
        list(
          taggedValue(
            typedDict({
              joinKey: 'string',
              joinObj: maybe(
                taggedValue(
                  typedDict({
                    table: maybe(
                      taggedValue(
                        typedDict({
                          file: file('json', {
                            columnTypes: {},
                            type: 'table',
                          }),
                        }),
                        maybe({
                          columnTypes: {},
                          type: 'table',
                        })
                      )
                    ),
                  }),
                  'number'
                )
              ),
            }),
            typedDict({
              '0': maybe(
                tableRowValueMaybeFile(
                  typedDict({
                    a: 'number',
                    b: 'number',
                    x: 'string',
                  })
                )
              ),
              '1': maybe(
                tableRowValueMaybeFile(
                  typedDict({
                    a: 'number',
                    b: 'number',
                    j: 'string',
                    x: 'string',
                  })
                )
              ),
            })
          )
        )
      )
    );
    expect(await client.query(joinedNode)).toEqual([
      [
        {
          '0': {a: 14, b: -1, x: 'cat'},
          '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
        },
        {
          '0': {a: 14, b: -1, x: 'cat'},
          '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
        },
        {
          '0': {a: 14, b: -2, x: 'dog'},
          '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
        },
        {
          '0': {a: 1, b: 2, x: 'dog'},
          '1': {a: 1, b: 21, j: 'j2', x: 'dog'},
        },
        {
          '0': {a: 9, b: 2, x: 'dog'},
          '1': {a: 9, b: 24, j: 'j3', x: 'roar'},
        },
      ],

      [
        {
          '0': {a: 14, b: -1, x: 'cat'},
          '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
        },
        {
          '0': {a: 14, b: -1, x: 'cat'},
          '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
        },
        {
          '0': {a: 14, b: -2, x: 'dog'},
          '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
        },
        {
          '0': {a: 1, b: 2, x: 'dog'},
          '1': {a: 1, b: 21, j: 'j2', x: 'dog'},
        },
        {
          '0': {a: 9, b: 2, x: 'dog'},
          '1': {a: 9, b: 24, j: 'j3', x: 'roar'},
        },
      ],
    ]);
  });

  it('mapped joined table', async () => {
    const client = await testClient();
    const joinedTable0 = getDSVizJoinedTable();
    const joinedTable1 = getDSVizJoinedTable();
    const joinedTableArr = opArray({
      0: joinedTable0,
      1: joinedTable1,
    } as any);
    const mappedRows = opMap({
      arr: joinedTableArr,
      mapFn: constFunction({row: joinedTableArr.type.objectType}, ({row}) => {
        return opJoinedTableRows({
          joinedTable: row,
          leftOuter: constBoolean(true),
          rightOuter: constBoolean(true),
        });
      }),
    });
    const mappedNode = await HL.refineNode(client, mappedRows, []);
    const jtData = [
      {
        '0': {a: 14, b: -1, x: 'cat'},
        '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
      },
      {
        '0': {a: 14, b: -1, x: 'cat'},
        '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
      },
      {
        '0': {a: 14, b: -2, x: 'dog'},
        '1': {a: 14, b: -2, j: 'j1', x: 'dog'},
      },
      {
        '0': {a: 1, b: 2, x: 'dog'},
        '1': {a: 1, b: 21, j: 'j2', x: 'dog'},
      },
      {
        '0': {a: 9, b: 2, x: 'dog'},
        '1': {a: 9, b: 24, j: 'j3', x: 'roar'},
      },
    ];
    const res = await client.query(mappedNode);
    expect(res).toEqual([jtData, jtData]);
  });

  it('partition table', async () => {
    const client = await testClient();
    const partitionedTable = getDSVizPartitionedTable();
    const partitionedTableRows = opPartitionedTableRows({
      partitionedTable: partitionedTable as any,
    });
    const partitionedTableRowsImproved = await HL.refineNode(
      client,
      partitionedTableRows,
      []
    );
    expect(partitionedTableRowsImproved.type).toEqual(
      list(
        tableRowValueMaybeFile(
          typedDict({a: 'number', b: 'string', c: 'boolean'})
        )
      )
    );
    expect(await client.query(partitionedTableRowsImproved)).toEqual([
      {a: 1, b: 'a', c: true},
      {a: 2, b: 'b', c: false},
      {a: 3, b: 'c', c: true},
      {a: 4, b: 'd', c: true},
      {a: 5, b: 'e', c: false},
      {a: 6, b: 'f', c: true},
      {a: 7, b: 'g', c: true},
      {a: 8, b: 'h', c: false},
      {a: 9, b: 'i', c: true},
    ]);
  });

  it('mapNodes can do a replace', async () => {
    const node: Node = {
      nodeType: 'output',
      type: 'number',
      fromOp: {
        name: 'x',
        inputs: {
          a: {
            nodeType: 'output',
            type: 'number',
            fromOp: {
              name: 'y',
              inputs: {
                c: {
                  nodeType: 'const',
                  type: 'number',
                  val: 2,
                },
              },
            },
          },
          b: {
            nodeType: 'const',
            type: 'number',
            val: 2,
          },
        },
      },
    };
    const findOp = node.fromOp;
    // Ensure the equality check in the predicate below works. It does as long
    // as nothing upstream of findOp has already been replaced.
    expect(
      mapNodes(node, n =>
        n.nodeType === 'output' && n.fromOp === findOp
          ? {nodeType: 'var', type: 'string', varName: 'a'}
          : n
      )
    ).toEqual({nodeType: 'var', type: 'string', varName: 'a'});
  });

  it('dropna', async () => {
    const client = await testClient();
    let node = opDropNa({
      arr: constNode(list('number'), [1, 2, 3, 4]),
    });
    expect(node.type).toEqual(list('number', 0));
    expect(await client.query(node)).toEqual([1, 2, 3, 4]);

    node = opDropNa({
      arr: constNode(list(maybe('number')), [1, 2, 3, 4]),
    });
    expect(node.type).toEqual(list('number', 0));
    expect(await client.query(node)).toEqual([1, 2, 3, 4]);

    node = opDropNa({
      arr: constNode(list(maybe('number')), [1, null, 3, null]),
    });
    expect(node.type).toEqual(list('number', 0));
    expect(await client.query(node)).toEqual([1, 3]);

    node = opDropNa({
      arr: constNode(
        taggedValue(
          'string',
          list(taggedValue('boolean', maybe(taggedValue('number', 'number'))))
        ),
        {
          _tag: 'hi',
          _value: [
            {
              _tag: {
                _tag: true,
                _value: 1,
              },
              _value: 2,
            },
            {
              _tag: false,
              _value: null,
            },
          ],
        }
      ),
    });
    expect(node.type).toEqual(
      taggedValue(
        'string',
        list(taggedValue(taggedValue('boolean', 'number'), 'number'), 0)
      )
    );
    expect(await client.query(node)).toEqual([2]);
    expect(await client.query(opGetTag({value: node}))).toEqual('hi');
    expect(
      await client.query(
        opGetTag({value: opIndex({arr: node, index: constNumber(0)})})
      )
    ).toEqual(1);
  });
});
