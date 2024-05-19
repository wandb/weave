/* tslint:disable */

import {forwardOpInputs, newForwardGraph} from './engine/forwardGraph';
import * as HL from './hl';
import type {OutputNode} from './model';
import {
  constBoolean,
  constFunction,
  constNone,
  constNumber,
  constString,
  file,
  hash,
  isListLike,
  isNullable,
  list,
  listObjectType,
  maybe,
  nullableTaggableValue,
  taggedValue,
  typedDict,
  union,
  varNode,
} from './model';
import {
  opArray,
  opArtifactVersionFile,
  opArtifactVersionFiles,
  opArtifactVersionName,
  opArtifactVersionSize,
  opCount,
  opDict,
  opFileJoinedTable,
  opFilePartitionedTable,
  opFilePath,
  opFileTable,
  opFilter,
  opGetProjectTag,
  opGetRunTag,
  opGroupby,
  opGroupGroupKey,
  opIndex,
  opJoinedTableRows,
  opLimit,
  opMap,
  opOffset,
  opPartitionedTableRows,
  opPick,
  opProjectCreatedAt,
  opProjectFilteredRuns,
  opProjectRun,
  opProjectRunQueues,
  opProjectRuns,
  opRootProject,
  opRootRepoInsightsUsersByCountry,
  opRunCreatedAt,
  opRunHeartbeatAt,
  opRunLoggedArtifactVersion,
  opRunLoggedArtifactVersions,
  opRunName,
  opRunQueueId,
  opRunSummary,
  opTableRows,
  opValues,
  toGqlField,
  toGqlQuery,
} from './ops';
import {testClient} from './testUtil';

function getFasionSweepRuns() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRuns = opProjectRuns({
    project: opRootProject({entityName, projectName}),
  });
  return fasionSweepRuns;
}

function getRepoInsightsPlotData() {
  const repoName = constString('pytorch');
  return opRootRepoInsightsUsersByCountry({repoName});
}

function getFasionSweepRunsName() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRuns = opProjectRuns({
    project: opRootProject({entityName, projectName}),
  });
  const offsetNode = opOffset({
    arr: fasionSweepRuns as any,
    offset: constNumber(1),
  });
  const limitNode = opLimit({
    arr: offsetNode as any,
    limit: constNumber(4),
  });
  const run0 = opIndex({
    arr: limitNode as any,
    index: constNumber(0),
  });
  const fasionSweepRunName = opRunName({run: run0 as any});
  return fasionSweepRunName;
}

function getFasionSweepRunName() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const fasionSweepRunName = opRunName({run: fasionSweepRun});
  return fasionSweepRunName;
}

function getFasionSweepRunSummary() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const fasionSweepRunSummary = opRunSummary({run: fasionSweepRun});
  return fasionSweepRunSummary;
}

function getFasionSweepRunSummaryTable() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const fasionSweepRunSummary = opRunSummary({run: fasionSweepRun});
  const table = opPick({
    obj: fasionSweepRunSummary,
    key: constString('table'),
  });
  return table;
}

function getFasionSweepRunSummaryJoinedTable() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const fasionSweepRunSummary = opRunSummary({run: fasionSweepRun});
  const table = opPick({
    obj: fasionSweepRunSummary,
    key: constString('joinedTable'),
  });
  return table;
}

function getFasionSweepRunSummaryPartitionedTable() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const fasionSweepRunSummary = opRunSummary({run: fasionSweepRun});
  const table = opPick({
    obj: fasionSweepRunSummary,
    key: constString('partitionedTable'),
  });
  return table;
}

function getFasionSweepRunLoggedArtifactSize() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const loggedArtifact = opRunLoggedArtifactVersion({
    run: fasionSweepRun as any,
    artifactVersionName: constString('train_results:v2'),
  });
  return opArtifactVersionSize({artifactVersion: loggedArtifact});
}

function getFasionSweepRunLoggedArtifactFilePaths() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const loggedArtifact = opRunLoggedArtifactVersion({
    run: fasionSweepRun as any,
    artifactVersionName: constString('train_results:v2'),
  });
  const files = opArtifactVersionFiles({artifactVersion: loggedArtifact});
  return opFilePath({file: files});
}

function getFasionSweepRunLoggedArtifactTable() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const loggedArtifact = opRunLoggedArtifactVersion({
    run: fasionSweepRun as any,
    artifactVersionName: constString('train_results:v2'),
  });
  const file = opArtifactVersionFile({
    artifactVersion: loggedArtifact,
    path: constString('train_iou_score_table.table.json'),
  });
  const table = opFileTable({
    file: file as any,
  });
  return table;
}

function getFasionSweepRunLoggedArtifactTables() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const loggedArtifact = opRunLoggedArtifactVersion({
    run: fasionSweepRun as any,
    artifactVersionName: constString('train_results:v2'),
  });
  const files = opArtifactVersionFile({
    artifactVersion: opArray({
      0: loggedArtifact,
      1: loggedArtifact,
      2: constNone(),
    } as any),
    path: constString('train_iou_score_table.table.json'),
  });
  const tables = opFileTable({
    file: files as any,
  });
  return tables;
}

function getFasionSweepRunLoggedArtifactsId() {
  const entityName = constString('shawn');
  const projectName = constString('fasion-sweep');
  const fasionSweepRun = opProjectRun({
    project: opRootProject({entityName, projectName}),
    runName: constString('1'),
  });
  const loggedArtifacts = opRunLoggedArtifactVersions({
    run: fasionSweepRun as any,
  });
  return opMap({
    arr: loggedArtifacts as any,
    mapFn: constFunction({row: 'artifactVersion'}, ({row}) =>
      opArtifactVersionName({
        artifactVersion: row,
      })
    ) as any,
  });
}

function expectGQLQueryToEqual(
  leafNode: OutputNode,
  rootNode: OutputNode,
  expectedQuery: any
) {
  const forwardGraph = newForwardGraph();
  forwardGraph.update(leafNode);
  const query = {
    queryFields: toGqlQuery(
      forwardGraph,
      forwardGraph.getOp(rootNode.fromOp) as any
    ),
  };
  expect(query).toEqual(expectedQuery);
}

describe('toGqlField', () => {
  it('project runs name', async () => {
    const node = getFasionSweepRunsName();
    const fg = newForwardGraph();
    fg.update(node);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlField(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            args: [
              {
                name: 'first',
                value: 100,
              },
            ],
            fields: [
              {
                fields: [
                  {
                    fields: [
                      {
                        fields: [],
                        name: 'id',
                      },
                      {
                        fields: [],
                        name: 'displayName',
                      },
                      {
                        fields: [],
                        name: 'name',
                      },
                    ],
                    name: 'node',
                  },
                ],
                name: 'edges',
              },
            ],
            name: 'runs',
          },
        ],
        name: 'project',
      },
    ]);
  });

  it('project run loggedartifact size', async () => {
    const node = getFasionSweepRunLoggedArtifactSize();
    const fg = newForwardGraph();
    fg.update(node);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlField(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            alias: 'run_1485272252048968',
            args: [
              {
                name: 'name',
                value: '1',
              },
            ],
            fields: [
              {
                fields: [],
                name: 'id',
              },
              {
                fields: [
                  {
                    fields: [
                      {
                        fields: [
                          {
                            fields: [],
                            name: 'id',
                          },
                          {
                            fields: [],
                            name: 'size',
                          },
                          {
                            fields: [],
                            name: 'versionIndex',
                          },
                          {
                            fields: [
                              {
                                fields: [],
                                name: 'id',
                              },
                              {
                                fields: [],
                                name: 'alias',
                              },
                            ],
                            name: 'aliases',
                          },
                          {
                            fields: [
                              {
                                fields: [],
                                name: 'id',
                              },
                              {
                                fields: [],
                                name: 'name',
                              },
                            ],
                            name: 'artifactSequence',
                          },
                        ],
                        name: 'node',
                      },
                    ],
                    name: 'edges',
                  },
                ],
                name: 'outputArtifacts',
              },
              {
                fields: [],
                name: 'name',
              },
            ],
            name: 'run',
          },
        ],
        name: 'project',
      },
    ]);
  });

  it('repo insights plot data', async () => {
    const node = getRepoInsightsPlotData();
    const plotName = 'rpt_weekly_users_by_country_by_repo';
    const fg = newForwardGraph();
    fg.update(node);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlField(fg, forwardOp);
    const opInputs = forwardOpInputs(fg, forwardOp);
    const alias = `repoInsights_${hash(opInputs.repoName)}_${hash(plotName)}`;
    expect(gqlFields).toEqual([
      {
        alias,
        name: 'repoInsightsPlotData',
        args: [
          {
            name: 'plotName',
            value: plotName,
          },
          {
            name: 'repoName',
            value: 'pytorch',
          },
          {
            name: 'first',
            value: 100000,
          },
        ],
        fields: [
          {
            name: 'edges',
            fields: [
              {
                name: 'node',
                fields: [
                  {
                    name: 'row',
                    fields: [],
                  },
                ],
              },
            ],
          },
          {
            name: 'schema',
            fields: [],
          },
          {
            name: 'isNormalizedUserCount',
            fields: [],
          },
        ],
      },
    ]);
  });
});

describe('execute', () => {
  it('project runs name', async () => {
    const client = await testClient();
    const node = getFasionSweepRunsName();
    expect(await client.query(node)).toEqual('frank');
  });

  it('project run name', async () => {
    const client = await testClient();
    const node = getFasionSweepRunName();
    expect(await client.query(node)).toEqual('frank');
  });

  it('repo insights plot data', async () => {
    const node = getRepoInsightsPlotData();
    const client = await testClient();
    expect(await client.query(node)).toEqual({
      rows: [
        {
          created_week: new Date(0),
          user_count: 1,
          framework: '1',
          country: '1',
        },
        {
          created_week: new Date(0),
          user_count: 2,
          framework: '2',
          country: '2',
        },
        {
          created_week: new Date(0),
          user_count: 3,
          framework: '3',
          country: '3',
        },
        {
          created_week: new Date(0),
          user_count: 4,
          framework: '4',
          country: '4',
        },
        {
          created_week: new Date(0),
          user_count: 5,
          framework: '5',
          country: '5',
        },
      ],
      isNormalizedUserCount: true,
    });
  });

  it('project run summary', async () => {
    const client = await testClient();
    const node = getFasionSweepRunSummary();
    const summaryNodeWithType = await HL.refineNode(client, node, []);
    expect(summaryNodeWithType.type).toEqual({
      tag: {
        tag: {
          tag: {
            propertyTypes: {entityName: 'string', projectName: 'string'},
            type: 'typedDict',
          },
          type: 'tagged',
          value: {
            propertyTypes: {project: 'project', runName: 'string'},
            type: 'typedDict',
          },
        },
        type: 'tagged',
        value: {propertyTypes: {run: 'run'}, type: 'typedDict'},
      },
      type: 'tagged',
      value: {
        propertyTypes: {
          table: {
            extension: 'json',
            type: 'file',
            wbObjectType: {type: 'table', columnTypes: {}},
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
    });
    expect(await client.query(node)).toEqual({
      table: {
        _type: 'table-file',
        artifact: {
          id: 'QXJ0aWZhY3Q6MjAwNzU5Mw==',
        },
        path: 'train_iou_score_table.table.json',
        artifact_path:
          'wandb-artifact://41727469666163743a32303037353933/train_iou_score_table.table.json',
        ncols: 3,
        size: 4687,
      },
      joinedTable: {
        _type: 'joined-table',
        artifact: {
          id: 'QXJ0aWZhY3Q6MjAwNzU5Mw==',
        },
        artifact_path: `wandb-artifact://41727469666163743a32303037353933/train-results.joined-table.json`,
        path: 'train-results.joined-table.json',
      },
      partitionedTable: {
        _type: 'partitioned-table',
        artifact: {
          id: 'QXJ0aWZhY3Q6MjAwNzU5Mw==',
        },
        artifact_path: `wandb-artifact://41727469666163743a32303037353933/part_table.partitioned-table.json`,
        path: 'part_table.partitioned-table.json',
      },
      x: -10.2,
      y: -1000,
      z: {a: 'hello', b: 99.1},
    });
  });

  it('project run summary table', async () => {
    const client = await testClient();
    const node = getFasionSweepRunSummaryTable();
    const summaryNodeWithType = await HL.refineNode(client, node, []);
    expect(summaryNodeWithType.type).toEqual({
      tag: {
        tag: {
          tag: {
            propertyTypes: {
              entityName: 'string',
              projectName: 'string',
            },
            type: 'typedDict',
          },
          type: 'tagged',
          value: {
            propertyTypes: {
              project: 'project',
              runName: 'string',
            },
            type: 'typedDict',
          },
        },
        type: 'tagged',
        value: {
          propertyTypes: {
            run: 'run',
          },
          type: 'typedDict',
        },
      },
      type: 'tagged',
      value: {
        extension: 'json',
        type: 'file',
        wbObjectType: {type: 'table', columnTypes: {}},
      },
    });

    // Note: this is checking an implementation detail. We may change this
    // format, users shouldn't interact with it. But "assetArtifactResolver"
    // depends on this format when it "looks up the graph" (for example when
    // you have an image in a table inside of an artifact), so test here
    // to ensure that doesnt break. A better test would be one that actually
    // checks an image in a table in an artifact from run summary.
    expect(await client.query(node)).toEqual({
      artifact: {id: 'QXJ0aWZhY3Q6MjAwNzU5Mw=='},
      path: 'train_iou_score_table.table.json',
      size: 4687,
      artifact_path:
        'wandb-artifact://41727469666163743a32303037353933/train_iou_score_table.table.json',
      ncols: 3,
      _type: 'table-file',
    });

    const table = opFileTable({file: summaryNodeWithType as any});
    const tableRows = opTableRows({
      table: table as any,
    });
    const rowCount = opCount({arr: tableRows as any});
    expect(await client.query(rowCount)).toEqual(5);
  });

  it('project run summary joined table', async () => {
    const client = await testClient();
    const node = getFasionSweepRunSummaryJoinedTable();
    const nodeWithType = await HL.refineNode(client, node, []);
    expect(nodeWithType.type).toEqual({
      tag: {
        tag: {
          tag: {
            propertyTypes: {
              entityName: 'string',
              projectName: 'string',
            },
            type: 'typedDict',
          },
          type: 'tagged',
          value: {
            propertyTypes: {
              project: 'project',
              runName: 'string',
            },
            type: 'typedDict',
          },
        },
        type: 'tagged',
        value: {
          propertyTypes: {
            run: 'run',
          },
          type: 'typedDict',
        },
      },
      type: 'tagged',
      value: {
        extension: 'json',
        type: 'file',
        wbObjectType: {type: 'joined-table', columnTypes: {}},
      },
    });
    expect(await client.query(node)).toEqual({
      _type: 'joined-table',
      artifact: {id: 'QXJ0aWZhY3Q6MjAwNzU5Mw=='},
      path: 'train-results.joined-table.json',
      artifact_path:
        'wandb-artifact://41727469666163743a32303037353933/train-results.joined-table.json',
    });
    const joinedTableNode = opFileJoinedTable({file: nodeWithType as any});
    const rowsNode = opJoinedTableRows({
      joinedTable: joinedTableNode as any,
      leftOuter: constBoolean(true),
      rightOuter: constBoolean(true),
    });
    const numRowsNode = opCount({
      arr: rowsNode as any,
    });
    expect(await client.query(numRowsNode)).toEqual(5);
  });

  it('project run summary partitioned table', async () => {
    const client = await testClient();
    const node = getFasionSweepRunSummaryPartitionedTable();
    const nodeWithType = await HL.refineNode(client, node, []);
    expect(nodeWithType.type).toEqual({
      tag: {
        tag: {
          tag: {
            propertyTypes: {
              entityName: 'string',
              projectName: 'string',
            },
            type: 'typedDict',
          },
          type: 'tagged',
          value: {
            propertyTypes: {
              project: 'project',
              runName: 'string',
            },
            type: 'typedDict',
          },
        },
        type: 'tagged',
        value: {
          propertyTypes: {
            run: 'run',
          },
          type: 'typedDict',
        },
      },
      type: 'tagged',
      value: {
        extension: 'json',
        type: 'file',
        wbObjectType: {type: 'partitioned-table', columnTypes: {}},
      },
    });
    expect(await client.query(node)).toEqual({
      _type: 'partitioned-table',
      artifact: {id: 'QXJ0aWZhY3Q6MjAwNzU5Mw=='},
      path: 'part_table.partitioned-table.json',
      artifact_path:
        'wandb-artifact://41727469666163743a32303037353933/part_table.partitioned-table.json',
    });
    const rows = opPartitionedTableRows({
      partitionedTable: opFilePartitionedTable({
        file: nodeWithType as any,
      }),
    });
    const numRowsNode = opCount({arr: rows});
    expect(await client.query(numRowsNode)).toEqual(9);
    const refined = await HL.refineNode(client, rows, []);
    expect(refined.type).toEqual(
      list(
        taggedValue(
          taggedValue(
            union([
              taggedValue(
                taggedValue(
                  typedDict({
                    entityName: 'string',
                    projectName: 'string',
                  }),
                  typedDict({project: 'project', runName: 'string'})
                ),
                typedDict({run: 'run'})
              ),
              taggedValue(
                taggedValue(
                  taggedValue(
                    typedDict({
                      entityName: 'string',
                      projectName: 'string',
                    }),
                    typedDict({
                      project: 'project',
                      runName: 'string',
                    })
                  ),
                  typedDict({run: 'run'})
                ),
                typedDict({
                  file: file('json', {
                    columnTypes: {},
                    type: 'table',
                  }),
                })
              ),
            ]),
            typedDict({
              table: maybe({columnTypes: {}, type: 'table'}),
            })
          ),
          typedDict({a: 'number', b: 'string', c: 'boolean'})
        )
      )
    );
  });

  it('project run loggedartifact size', async () => {
    const client = await testClient();
    const node = getFasionSweepRunLoggedArtifactSize();
    expect(await client.query(node)).toEqual(1921);
  });

  it('project run loggedartifact files paths', async () => {
    const client = await testClient();
    const node = getFasionSweepRunLoggedArtifactFilePaths();
    expect(await client.query(node)).toEqual([
      't1.table.json',
      't2.table.json',
      't3.table.json',
    ]);
  });

  it('project run loggedartifact table', async () => {
    const client = await testClient();
    const node = getFasionSweepRunLoggedArtifactTable();
    const tableRows = opTableRows({
      table: node as any,
    });
    const rowCount = opCount({arr: tableRows as any});
    expect(await client.query(rowCount)).toEqual(5);
  });

  it('project run loggedartifact tables', async () => {
    const client = await testClient();
    const tablesNode = getFasionSweepRunLoggedArtifactTables();

    // Make sure the refinement returns the correct type
    const refinedTablesNode = await HL.refineNode(client, tablesNode, []);
    expect(isListLike(refinedTablesNode.type)).toBeTruthy();
    expect(isNullable(listObjectType(refinedTablesNode.type))).toBeTruthy();
    expect(
      nullableTaggableValue(listObjectType(refinedTablesNode.type)) as any
    ).toEqual({type: 'table', columnTypes: {}});

    // Make sure that the results are mapped properly
    const tablesRows = opTableRows({
      table: tablesNode as any,
    });
    const row0Count = opCount({
      arr: opIndex({arr: tablesRows, index: constNumber(0)}) as any,
    });
    expect(await client.query(row0Count)).toEqual(5);
    const row1Count = opCount({
      arr: opIndex({arr: tablesRows, index: constNumber(1)}) as any,
    });
    expect(await client.query(row1Count)).toEqual(5);
    const row2Count = opCount({
      arr: opIndex({arr: tablesRows, index: constNumber(2)}) as any,
    });
    expect(await client.query(row2Count)).toEqual(null);
  });

  it('project run loggedartifacts id', async () => {
    const client = await testClient();
    const node = getFasionSweepRunLoggedArtifactsId();
    expect(await client.query(node)).toEqual([
      'train_results:v2',
      'train_results:v3',
    ]);
  });

  it('run summary array with variable index refined type', async () => {
    const client = await testClient();
    const runs = getFasionSweepRuns();
    const allSummaries = opRunSummary({
      run: opIndex({arr: runs, index: varNode('number', 'n')}),
    });
    const summaryNodeWithType = await HL.refineNode(client, allSummaries, []);
    expect(summaryNodeWithType.type).toEqual({
      tag: {
        tag: {
          tag: {
            propertyTypes: {entityName: 'string', projectName: 'string'},
            type: 'typedDict',
          },
          type: 'tagged',
          value: {propertyTypes: {project: 'project'}, type: 'typedDict'},
        },
        type: 'tagged',
        value: {propertyTypes: {run: 'run'}, type: 'typedDict'},
      },
      type: 'tagged',
      value: {
        members: [
          {propertyTypes: {x: 'number', y: 'number'}, type: 'typedDict'},
          {
            propertyTypes: {
              joinedTable: {
                extension: 'json',
                type: 'file',
                wbObjectType: {columnTypes: {}, type: 'joined-table'},
              },
              partitionedTable: {
                extension: 'json',
                type: 'file',
                wbObjectType: {columnTypes: {}, type: 'partitioned-table'},
              },
              table: {
                extension: 'json',
                type: 'file',
                wbObjectType: {columnTypes: {}, type: 'table'},
              },
              x: 'number',
              y: 'number',
              z: typedDict({a: 'string', b: 'number'}),
            },
            type: 'typedDict',
          },
        ],
        type: 'union',
      },
    });
  });
  it('double run summary array with variable index refined type', async () => {
    const client = await testClient();
    const runs = getFasionSweepRuns();
    // grouping creates run[][]
    const groupedRuns = opGroupby({
      arr: runs,
      groupByFn: constFunction({row: 'run'}, ({row}) =>
        opPick({
          obj: opRunSummary({
            run: varNode('run', 'row') as any,
          }),
          key: constString('y'),
        })
      ),
    });
    const allSummaries = opRunSummary({
      run: opIndex({
        arr: groupedRuns,
        index: varNode('number', 'n'),
      }),
    });
    const summaryNodeWithType = await HL.refineNode(client, allSummaries, []);
    expect(summaryNodeWithType.type).toEqual({
      tag: {
        tag: {
          tag: {
            tag: {
              tag: {
                tag: {
                  propertyTypes: {entityName: 'string', projectName: 'string'},
                  type: 'typedDict',
                },
                type: 'tagged',
                value: {propertyTypes: {project: 'project'}, type: 'typedDict'},
              },
              type: 'tagged',
              value: {
                propertyTypes: {entityName: 'string', projectName: 'string'},
                type: 'typedDict',
              },
            },
            type: 'tagged',
            value: {propertyTypes: {project: 'project'}, type: 'typedDict'},
          },
          type: 'tagged',
          value: {propertyTypes: {run: 'run'}, type: 'typedDict'},
        },
        type: 'tagged',
        value: {propertyTypes: {groupKey: 'number'}, type: 'typedDict'},
      },
      type: 'tagged',
      value: {
        objectType: {
          tag: {propertyTypes: {run: 'run'}, type: 'typedDict'},
          type: 'tagged',
          value: {
            members: [
              {propertyTypes: {x: 'number', y: 'number'}, type: 'typedDict'},
              {
                propertyTypes: {
                  joinedTable: {
                    extension: 'json',
                    type: 'file',
                    wbObjectType: {columnTypes: {}, type: 'joined-table'},
                  },
                  partitionedTable: {
                    extension: 'json',
                    type: 'file',
                    wbObjectType: {columnTypes: {}, type: 'partitioned-table'},
                  },
                  table: {
                    extension: 'json',
                    type: 'file',
                    wbObjectType: {columnTypes: {}, type: 'table'},
                  },
                  x: 'number',
                  y: 'number',
                  z: typedDict({a: 'string', b: 'number'}),
                },
                type: 'typedDict',
              },
            ],
            type: 'union',
          },
        },
        type: 'list',
      },
    });
  });
});

describe('toGqlQuery', () => {
  it('correctly merges run.summaryMetrics fields w/ different keys', async () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const fasionSweepRun = opProjectRun({
      project: opRootProject({entityName, projectName}),
      runName: constString('1'),
    });
    const fasionSweepRunSummary = opRunSummary({run: fasionSweepRun});
    const node1 = opPick({
      obj: fasionSweepRunSummary,
      key: constString('_runtime'),
    });
    const node2 = opPick({
      obj: fasionSweepRunSummary,
      key: constString('_timestamp'),
    });
    const fg = newForwardGraph();
    fg.update(node1);
    fg.update(node2);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlQuery(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            alias: 'run_1485272252048968',
            args: [
              {
                name: 'name',
                value: '1',
              },
            ],
            fields: [
              {
                fields: [],
                name: 'id',
              },
              {
                fields: [],
                name: 'summaryMetrics',
              },
              {
                fields: [],
                name: 'name',
              },
            ],
            name: 'run',
          },
        ],
        name: 'project',
      },
    ]);
  });

  it('correctly merges run.summaryMetrics fields w/ keys and no keys', async () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const fasionSweepRun = opProjectRun({
      project: opRootProject({entityName, projectName}),
      runName: constString('1'),
    });
    const fasionSweepRunSummary = opRunSummary({run: fasionSweepRun});
    const node1 = opValues({
      obj: fasionSweepRunSummary,
    });
    const node2 = opPick({
      obj: fasionSweepRunSummary,
      key: constString('_timestamp'),
    });
    const fg = newForwardGraph();
    fg.update(node1);
    fg.update(node2);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlQuery(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            alias: 'run_1485272252048968',
            args: [
              {
                name: 'name',
                value: '1',
              },
            ],
            fields: [
              {
                fields: [],
                name: 'id',
              },
              {
                fields: [],
                name: 'summaryMetrics',
              },
              {
                fields: [],
                name: 'name',
              },
            ],
            name: 'run',
          },
        ],
        name: 'project',
      },
    ]);
  });

  it('overrides default limits for paginated ops with immediate opLimit child', async () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const fasionSweepRuns = opProjectRuns({
      project: opRootProject({entityName, projectName}),
    });
    const limitedRuns = opLimit({
      arr: fasionSweepRuns,
      limit: constNumber(1234),
    });
    const fasionSweepRunSummary = opRunSummary({run: limitedRuns});
    const fg = newForwardGraph();
    fg.update(fasionSweepRunSummary);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlQuery(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            args: [
              {
                name: 'first',
                value: 1234,
              },
            ],
            fields: [
              {
                fields: [
                  {
                    fields: [
                      {
                        fields: [],
                        name: 'id',
                      },
                      {
                        fields: [],
                        name: 'summaryMetrics',
                      },
                      {
                        fields: [],
                        name: 'name',
                      },
                    ],
                    name: 'node',
                  },
                ],
                name: 'edges',
              },
            ],
            name: 'runs',
          },
        ],
        name: 'project',
      },
    ]);
  });

  it('uses default limits for paginated ops with no immediate opLimit child', async () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const fasionSweepRuns = opProjectRuns({
      project: opRootProject({entityName, projectName}),
    });
    const fasionSweepRunSummary = opRunSummary({run: fasionSweepRuns});
    const fg = newForwardGraph();
    fg.update(fasionSweepRunSummary);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlQuery(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            args: [
              {
                name: 'first',
                value: 100,
              },
            ],
            fields: [
              {
                fields: [
                  {
                    fields: [
                      {
                        fields: [],
                        name: 'id',
                      },
                      {
                        fields: [],
                        name: 'summaryMetrics',
                      },
                      {
                        fields: [],
                        name: 'name',
                      },
                    ],
                    name: 'node',
                  },
                ],
                name: 'edges',
              },
            ],
            name: 'runs',
          },
        ],
        name: 'project',
      },
    ]);
  });

  it('propagates tag requests appropriately - simple linear', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opIndex({arr: node, index: constNumber(0)});
    node = opPick({obj: node, key: constString('col_x')});
    node = opGetRunTag({obj: node});
    node = opRunHeartbeatAt({run: node});
    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'heartbeatAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
          ],
          name: 'project',
        },
      ],
    });
  });

  it('propagates tag requests appropriately - nested linear', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opIndex({arr: node, index: constNumber(0)});
    node = opPick({obj: node, key: constString('col_x')});
    node = opGetRunTag({obj: node});
    node = opRunHeartbeatAt({run: node});
    node = opGetProjectTag({obj: node});
    node = opProjectCreatedAt({obj: node});
    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'heartbeatAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
            {
              args: undefined,
              fields: [],
              name: 'createdAt',
            },
          ],
          name: 'project',
        },
      ],
    });
  });

  it('propagates tag requests appropriately - nested dual linear', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opIndex({arr: node, index: constNumber(0)});
    node = opPick({obj: node, key: constString('col_x')});
    node = opGetRunTag({obj: node});
    node = opRunHeartbeatAt({run: node});
    node = opGetProjectTag({obj: node});
    node = opProjectCreatedAt({project: node});
    node = opGetProjectTag({obj: node});
    node = opProjectFilteredRuns({
      project: node,
      filter: constString('__FILTER_PLACEHOLDER__'),
      order: constString('__ORDER_PLACEHOLDER__'),
    });
    node = opRunName({run: node});
    node = opGetRunTag({obj: node});
    node = opRunCreatedAt({run: node});

    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'heartbeatAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
            {
              args: undefined,
              fields: [],
              name: 'createdAt',
            },
            {
              alias: 'filteredRuns_5892705260744319',
              args: [
                {
                  name: 'first',
                  value: 100,
                },
                {
                  name: 'filters',
                  value: '__FILTER_PLACEHOLDER__',
                },
                {
                  name: 'order',
                  value: '__ORDER_PLACEHOLDER__',
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'displayName',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'createdAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
          ],
          name: 'project',
        },
      ],
    });
  });
  it('propagates tag requests appropriately - groupby also consumes', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opGroupby({
      arr: node,
      groupByFn: constFunction(
        {
          row: typedDict({
            col_s: 'string',
            col_n: 'number',
            col_b: 'boolean',
          }),
        },
        ({row}) => {
          let innerNode = opPick({
            obj: row,
            key: constString('col_s'),
          });
          innerNode = opGetRunTag({obj: innerNode});
          innerNode = opRunHeartbeatAt({run: innerNode});
          return innerNode;
        }
      ),
    });
    node = opIndex({arr: node, index: constNumber(0)});
    node = opPick({obj: node, key: constString('col_x')});
    node = opGetRunTag({obj: node});
    node = opRunCreatedAt({run: node});

    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'heartbeatAt',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'createdAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
          ],
          name: 'project',
        },
      ],
    });
  });

  it('propagates tag requests appropriately - groupby a tagged value', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opGroupby({
      arr: node,
      groupByFn: constFunction(
        {
          row: typedDict({
            col_s: 'string',
            col_n: 'number',
            col_b: 'boolean',
          }),
        },
        ({row}) => {
          let innerNode = opPick({
            obj: row,
            key: constString('col_s'),
          });
          innerNode = opGetProjectTag({obj: innerNode});
          innerNode = opProjectFilteredRuns({
            project: innerNode,
            filter: constString('__FILTER_PLACEHOLDER__'),
            order: constString('__ORDER_PLACEHOLDER__'),
          });
          innerNode = opRunName({run: innerNode});
          innerNode = opGetRunTag({obj: innerNode});
          return innerNode;
        }
      ),
    });
    node = opIndex({arr: node, index: constNumber(0)});
    node = opGroupGroupKey({obj: node});
    node = opRunCreatedAt({run: node});

    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
            {
              alias: 'filteredRuns_5892705260744319',
              args: [
                {
                  name: 'first',
                  value: 100,
                },
                {
                  name: 'filters',
                  value: '__FILTER_PLACEHOLDER__',
                },
                {
                  name: 'order',
                  value: '__ORDER_PLACEHOLDER__',
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'displayName',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'createdAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
          ],
          name: 'project',
        },
      ],
    });
  });

  it('propagates tag requests appropriately - groupby a tagged value (dict)', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opGroupby({
      arr: node,
      groupByFn: constFunction(
        {
          row: typedDict({
            col_s: 'string',
            col_n: 'number',
            col_b: 'boolean',
          }),
        },
        ({row}) => {
          let innerNode = opPick({
            obj: row,
            key: constString('col_s'),
          });
          innerNode = opGetProjectTag({obj: innerNode});
          innerNode = opProjectFilteredRuns({
            project: innerNode,
            filter: constString('__FILTER_PLACEHOLDER__'),
            order: constString('__ORDER_PLACEHOLDER__'),
          });
          innerNode = opRunName({run: innerNode});
          innerNode = opGetRunTag({obj: innerNode});
          innerNode = opDict({
            new_col: innerNode,
          } as any);
          return innerNode;
        }
      ),
    });
    node = opIndex({arr: node, index: constNumber(0)});
    node = opGroupGroupKey({obj: node});
    node = opPick({obj: node, key: constString('new_col')});
    node = opRunCreatedAt({run: node});

    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
            {
              alias: 'filteredRuns_5892705260744319',
              args: [
                {
                  name: 'first',
                  value: 100,
                },
                {
                  name: 'filters',
                  value: '__FILTER_PLACEHOLDER__',
                },
                {
                  name: 'order',
                  value: '__ORDER_PLACEHOLDER__',
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'displayName',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'createdAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
          ],
          name: 'project',
        },
      ],
    });
  });

  it('propagates tag requests appropriately - filter lambda', () => {
    const rootNode = opRootProject({
      entityName: constString('entity_a'),
      projectName: constString('project_a'),
    });
    let node = opProjectRuns({project: rootNode});
    node = opRunSummary({run: node});
    node = opPick({obj: node, key: constString('table')});
    node = opFileTable({file: node});
    node = opTableRows({table: node});
    node = opFilter({
      arr: node,
      filterFn: constFunction(
        {
          row: typedDict({
            col_s: 'string',
            col_n: 'number',
            col_b: 'boolean',
          }),
        },
        ({row}) => {
          let innerNode = opPick({
            obj: row,
            key: constString('col_s'),
          });
          innerNode = opGetProjectTag({obj: innerNode});
          innerNode = opProjectFilteredRuns({
            project: innerNode,
            filter: constString('__FILTER_PLACEHOLDER__'),
            order: constString('__ORDER_PLACEHOLDER__'),
          });
          innerNode = opRunName({run: innerNode});
          innerNode = opGetRunTag({obj: innerNode});
          innerNode = opRunHeartbeatAt({run: innerNode});
          return innerNode;
        }
      ),
    });
    node = opIndex({arr: node, index: constNumber(0)});
    expectGQLQueryToEqual(node, rootNode, {
      queryFields: [
        {
          alias: 'project_7796995639162091',
          args: [
            {
              name: 'entityName',
              value: 'entity_a',
            },
            {
              name: 'name',
              value: 'project_a',
            },
          ],
          fields: [
            {
              fields: [],
              name: 'id',
            },
            {
              args: [
                {
                  name: 'first',
                  value: 100,
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          fields: [],
                          name: 'summaryMetrics',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
            {
              alias: 'filteredRuns_5892705260744319',
              args: [
                {
                  name: 'first',
                  value: 100,
                },
                {
                  name: 'filters',
                  value: '__FILTER_PLACEHOLDER__',
                },
                {
                  name: 'order',
                  value: '__ORDER_PLACEHOLDER__',
                },
              ],
              fields: [
                {
                  fields: [
                    {
                      alias: undefined,
                      args: undefined,
                      fields: [
                        {
                          fields: [],
                          name: 'id',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'displayName',
                        },
                        {
                          args: undefined,
                          fields: [],
                          name: 'heartbeatAt',
                        },
                        {
                          fields: [],
                          name: 'name',
                        },
                      ],
                      name: 'node',
                    },
                  ],
                  name: 'edges',
                },
              ],
              name: 'runs',
            },
          ],
          name: 'project',
        },
      ],
    });
  });
  it('fetches runQueue related keys', () => {
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');

    const runQueues = opRunQueueId({
      runQueue: opProjectRunQueues({
        project: opRootProject({entityName, projectName}),
      }),
    });
    const fg = newForwardGraph();
    fg.update(runQueues);
    const forwardOp = Array.from(fg.getRoots())[0];
    const gqlFields = toGqlQuery(fg, forwardOp);
    expect(gqlFields).toEqual([
      {
        alias: 'project_163607767109650',
        args: [
          {
            name: 'entityName',
            value: 'shawn',
          },
          {
            name: 'name',
            value: 'fasion-sweep',
          },
        ],
        fields: [
          {
            fields: [],
            name: 'id',
          },
          {
            fields: [
              {
                fields: [],
                name: 'id',
              },
            ],
            name: 'runQueues',
          },
        ],
        name: 'project',
      },
    ]);
  });
});
