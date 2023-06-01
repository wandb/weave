import {refineNode} from './hl';
import {defaultLanguageBinding} from './language';
import {
  constBoolean,
  constFunction,
  constNone,
  constNumber,
  constString,
  file,
  findNamedTagInType,
  isAssignableTo,
  list,
  listObjectType,
  maybe,
  tableRowValue,
  taggedValue,
  typedDict,
  union,
  varNode,
  withFileTag,
  withNamedTag,
  withTableRowTag,
} from './model';
import {
  opArray,
  opArtifactVersionFile,
  opAssetArtifactVersion,
  opConcat,
  opFileTable,
  opGetJoinedJoinObj,
  opGetProjectTag,
  opGetRunTag,
  opGroupby,
  opIndex,
  opJoin,
  opJoinAll,
  opMap,
  opPick,
  opProjectInternalId,
  opProjectRun,
  opProjectRuns,
  opRootArtifactVersion,
  opRootProject,
  opRunInternalId,
  opRunSummary,
  opTableRows,
  opTableRowTable,
} from './ops';
import {testClient} from './testUtil';

const AV0_VALUE = {id: 2};
const AV1_VALUE = {id: 3};
const AV2_VALUE = {id: 4};
const AV3_VALUE = {id: 5};

function getTablesFromDifferentArtifacts() {
  const artifactVersion0 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v0'),
  });
  const artifactFile0 = opArtifactVersionFile({
    artifactVersion: artifactVersion0,
    path: constString('media_table.table.json'),
  });
  const table0 = opFileTable({file: artifactFile0 as any});

  const artifactVersion4 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v4'),
  });
  const artifactFile4 = opArtifactVersionFile({
    artifactVersion: artifactVersion4,
    path: constString('media_table.table.json'),
  });
  const table1 = opFileTable({file: artifactFile4 as any});

  const tableNull = opFileTable({file: constNone()});

  return {table0, table1, tableNull};
}

function getTableRowsFromDifferentArtifacts() {
  const artifactVersion0 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v0'),
  });
  const artifactFile0 = opArtifactVersionFile({
    artifactVersion: artifactVersion0,
    path: constString('media_table.table.json'),
  });
  const table0 = opFileTable({file: artifactFile0 as any});
  const tableRows0 = opTableRows({
    table: table0 as any,
  });

  const artifactVersion1 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v1'),
  });
  const artifactFile1 = opArtifactVersionFile({
    artifactVersion: artifactVersion1,
    path: constString('media_table.table.json'),
  });
  const table1 = opFileTable({file: artifactFile1 as any});
  const tableRows1 = opTableRows({
    table: table1 as any,
  });

  const artifactVersion2 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v2'),
  });
  const artifactFile2 = opArtifactVersionFile({
    artifactVersion: artifactVersion2,
    path: constString('media_table.table.json'),
  });
  const table2 = opFileTable({file: artifactFile2 as any});
  const tableRows2 = opTableRows({
    table: table2 as any,
  });

  const artifactVersion3 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v3'),
  });
  const artifactFile3 = opArtifactVersionFile({
    artifactVersion: artifactVersion3,
    path: constString('media_table.table.json'),
  });
  const table3 = opFileTable({file: artifactFile3 as any});
  const tableRows3 = opTableRows({
    table: table3 as any,
  });

  return {tableRows0, tableRows1, tableRows2, tableRows3};
}

function getLinkedTable() {
  const artifactVersion3 = opRootArtifactVersion({
    entityName: constString('shawn'),
    projectName: constString('many_tables'),
    artifactTypeName: constString('dataset'),
    artifactVersionName: constString('tables:v3'),
  });
  const artifactFile3 = opArtifactVersionFile({
    artifactVersion: artifactVersion3,
    path: constString('linked_table.table.json'),
  });
  const table3 = opFileTable({file: artifactFile3 as any});
  return opTableRows({
    table: table3 as any,
  });
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

describe('new parent child behavior', () => {
  it('all test tables come from different artifacts', async () => {
    const client = await testClient();
    const {tableRows0, tableRows1, tableRows2, tableRows3} =
      getTableRowsFromDifferentArtifacts();

    const img00 = opPick({
      obj: opIndex({arr: tableRows0 as any, index: constNumber(0)}),
      key: constString('img'),
    });

    const img00ArtifactVersion = opAssetArtifactVersion({
      asset: img00 as any,
    });
    expect(await client.query(img00ArtifactVersion)).toEqual(AV0_VALUE);

    const img10 = opPick({
      obj: opIndex({arr: tableRows1 as any, index: constNumber(0)}),
      key: constString('img'),
    });
    const img10ArtifactVersion = opAssetArtifactVersion({
      asset: img10 as any,
    });
    expect(await client.query(img10ArtifactVersion)).toEqual(AV1_VALUE);

    const img20 = opPick({
      obj: opIndex({arr: tableRows2 as any, index: constNumber(0)}),
      key: constString('img'),
    });
    const img20ArtifactVersion = opAssetArtifactVersion({
      asset: img20 as any,
    });
    expect(await client.query(img20ArtifactVersion)).toEqual(AV2_VALUE);

    const img30 = opPick({
      obj: opIndex({arr: tableRows3 as any, index: constNumber(0)}),
      key: constString('img'),
    });
    const img30ArtifactVersion = opAssetArtifactVersion({
      asset: img30 as any,
    });
    expect(await client.query(img30ArtifactVersion)).toEqual(AV3_VALUE);
  });

  // TODO: haven't fixed join yet
  it('join 2 tables', async () => {
    const client = await testClient();
    let {tableRows0, tableRows1} = getTableRowsFromDifferentArtifacts();
    tableRows0 = (await refineNode(
      client,
      tableRows0,
      []
    )) as typeof tableRows0;
    tableRows1 = (await refineNode(
      client,
      tableRows1,
      []
    )) as typeof tableRows1;
    const joined = opJoin({
      arr1: tableRows0 as any,
      arr2: tableRows1 as any,
      join1Fn: constFunction({row: listObjectType(tableRows0.type)}, ({row}) =>
        opPick({obj: row, key: constString('id')})
      ) as any,
      join2Fn: constFunction({row: listObjectType(tableRows1.type)}, ({row}) =>
        opPick({obj: row, key: constString('id')})
      ) as any,
      alias1: constString('0'),
      alias2: constString('1'),
      leftOuter: constBoolean(true),
      rightOuter: constBoolean(true),
    });

    const row0 = opIndex({arr: joined as any, index: constNumber(0)});

    const img00 = opPick({
      obj: row0 as any,
      key: constString('0.img'),
    });
    const img00ArtifactVersion = opAssetArtifactVersion({
      asset: img00 as any,
    });
    expect(await client.query(img00ArtifactVersion)).toEqual(AV0_VALUE);

    const img10 = opPick({
      obj: row0 as any,
      key: constString('1.img'),
    });
    const img10ArtifactVersion = opAssetArtifactVersion({
      asset: img10 as any,
    });
    expect(await client.query(img10ArtifactVersion)).toEqual(AV1_VALUE);
  });

  it('join 2 tables on img', async () => {
    const client = await testClient();
    let {tableRows0, tableRows1} = getTableRowsFromDifferentArtifacts();
    tableRows0 = (await refineNode(
      client,
      tableRows0,
      []
    )) as typeof tableRows0;
    tableRows1 = (await refineNode(
      client,
      tableRows1,
      []
    )) as typeof tableRows1;
    const join1Fn = constFunction(
      {row: listObjectType(tableRows0.type)},
      ({row}) =>
        opPick({
          obj: row,
          key: constString('img'),
        })
    );
    const join2Fn = constFunction(
      {row: listObjectType(tableRows1.type)},
      ({row}) =>
        opPick({
          obj: row,
          key: constString('img'),
        })
    );
    const joined = opJoin({
      arr1: tableRows0 as any,
      arr2: tableRows1 as any,
      join1Fn: join1Fn as any,
      join2Fn: join2Fn as any,
      alias1: constString('0'),
      alias2: constString('1'),
      leftOuter: constBoolean(true),
      rightOuter: constBoolean(true),
    });

    expect((await client.query(joined)).length).toEqual(3);
    const row0 = opIndex({arr: joined as any, index: constNumber(0)});
    const img00 = opPick({
      obj: row0 as any,
      key: constString('0.img'),
    });
    const img00ArtifactVersion = opAssetArtifactVersion({
      asset: img00 as any,
    });
    expect(await client.query(img00ArtifactVersion)).toEqual(AV0_VALUE);
    const img10 = opPick({
      obj: row0 as any,
      key: constString('1.img'),
    });
    const img10ArtifactVersion = opAssetArtifactVersion({
      asset: img10 as any,
    });
    expect(await client.query(img10ArtifactVersion)).toEqual(AV1_VALUE);
  });

  it('join all 4 tables on img', async () => {
    const client = await testClient();
    let {tableRows0, tableRows1, tableRows2, tableRows3} =
      getTableRowsFromDifferentArtifacts();
    tableRows0 = (await refineNode(
      client,
      tableRows0,
      []
    )) as typeof tableRows0;
    tableRows1 = (await refineNode(
      client,
      tableRows1,
      []
    )) as typeof tableRows1;
    tableRows2 = (await refineNode(
      client,
      tableRows2,
      []
    )) as typeof tableRows2;
    tableRows3 = (await refineNode(
      client,
      tableRows3,
      []
    )) as typeof tableRows3;

    const joined = opJoinAll({
      arrs: opArray({
        0: tableRows0,
        1: tableRows1,
        2: tableRows2,
        3: tableRows3,
      } as any) as any,
      joinFn: constFunction({row: listObjectType(tableRows0.type)}, ({row}) =>
        opPick({
          obj: row,
          key: constString('img'),
        })
      ) as any,
      outer: constBoolean(true),
    });

    expect((await client.query(joined)).length).toEqual(3);
    const row0 = opIndex({arr: joined as any, index: constNumber(0)});
    const img0 = opPick({
      obj: row0 as any,
      key: constString('img'),
    });
    expect(await client.query(img0)).toEqual([
      {
        _type: 'image-file',
        format: 'png',
        height: 360,
        path: 'media/images/0.png',
        width: 640,
      },
      {
        _type: 'image-file',
        format: 'png',
        height: 100,
        path: 'media/images/0.png',
        width: 100,
      },
      {
        _type: 'image-file',
        format: 'png',
        height: 200,
        path: 'media/images/0.png',
        width: 100,
      },
      {
        _type: 'image-file',
        format: 'png',
        height: 200,
        path: 'media/images/0.png',
        width: 200,
      },
    ]);

    const row0Obj = opGetJoinedJoinObj({obj: row0});
    const row0ObjArtifactVersion = opAssetArtifactVersion({
      asset: row0Obj as any,
    });
    expect(await client.query(row0ObjArtifactVersion)).toEqual(AV3_VALUE);
  });

  it('group 2 tables on img', async () => {
    const client = await testClient();
    const {tableRows0, tableRows1} = getTableRowsFromDifferentArtifacts();
    let combined = opConcat({
      arr: opArray({0: tableRows0, 1: tableRows1} as any),
    });
    combined = (await refineNode(client, combined, [])) as typeof combined;
    const grouped = opGroupby({
      arr: combined,
      groupByFn: constFunction({row: listObjectType(combined.type)}, ({row}) =>
        opPick({
          obj: row as any,
          key: constString('img'),
        })
      ),
    });

    const res = await client.query(grouped);
    expect(res.length).toEqual(3);
    const row0 = opIndex({arr: grouped as any, index: constNumber(0)});
    const img0 = opPick({
      obj: row0 as any,
      key: constString('img'),
    });
    expect(await client.query(img0)).toEqual([
      {
        _type: 'image-file',
        format: 'png',
        height: 360,
        path: 'media/images/0.png',
        width: 640,
      },
      {
        _type: 'image-file',
        format: 'png',
        height: 100,
        path: 'media/images/0.png',
        width: 100,
      },
    ]);
  });

  it('concat 2 tables', async () => {
    const client = await testClient();
    const {tableRows0, tableRows1} = getTableRowsFromDifferentArtifacts();

    const concated = opConcat({
      arr: opArray({0: tableRows0, 1: tableRows1} as any) as any,
    });

    const imgCol = opPick({
      obj: concated,
      key: constString('img'),
    });
    const imgColWithType = await refineNode(client, imgCol, []);
    expect(defaultLanguageBinding.printType(imgColWithType.type, false))
      .toEqual(`List<Tagged<
  tag: Tagged<
    tag: {
      file:File<Table>
    }
    value: {
      table:Maybe<Table>
    }
  >
  value: image-file
>>`);

    const img0 = opIndex({
      arr: imgColWithType as any,
      index: constNumber(0),
    });
    const img0ArtifactVersion = opAssetArtifactVersion({
      asset: img0 as any,
    });
    expect(await client.query(img0ArtifactVersion)).toEqual(AV0_VALUE);
    const img3 = opIndex({
      arr: imgColWithType as any,
      index: constNumber(3),
    });
    const img3ArtifactVersion = opAssetArtifactVersion({
      asset: img3 as any,
    });
    expect(await client.query(img3ArtifactVersion)).toEqual(AV1_VALUE);

    // Should be able to get artifact versions by mapping
    const allImgArtifactVersions = opMap({
      arr: imgColWithType as any,
      mapFn: constFunction({row: img3.type}, ({row}) =>
        opAssetArtifactVersion({
          asset: row,
        })
      ) as any,
    });
    // Yes! this works!
    expect(await client.query(allImgArtifactVersions)).toEqual([
      {id: 2},
      {id: 2},
      {id: 2},
      {id: 3},
      {id: 3},
      {id: 3},
    ]);

    expect(
      await client.query(opPick({obj: concated, key: constString('id')}))
    ).toEqual([0, 1, 2, 0, 1, 2]);
  });

  it('table rows tagged', async () => {
    const client = await testClient();

    const {tableRows0} = getTableRowsFromDifferentArtifacts();
    // expect(TypeHelpers.toString(tableRows0.type)).toEqual(

    // );
    const row0 = opIndex({arr: tableRows0 as any, index: constNumber(0)});
    const row0WithType = await refineNode(client, row0, []);
    expect(row0WithType.type).toEqual(
      withTableRowTag(
        typedDict({
          id: 'id',
          img: {
            boxLayers: {},
            boxScoreKeys: [],
            classMap: {},
            maskLayers: {},
            type: 'image-file',
          },
          str: 'string',
        }),
        withFileTag(
          maybe({type: 'table', columnTypes: {}}),
          file('json', {type: 'table', columnTypes: {}})
        )
      )
    );

    const table = opTableRowTable({obj: row0});
    const tableArtifactVersion = opAssetArtifactVersion({
      asset: table as any,
    });
    expect(await client.query(tableArtifactVersion)).toEqual(AV0_VALUE);
  });

  it('table row pick tagged', async () => {
    const client = await testClient();

    const {tableRows0} = getTableRowsFromDifferentArtifacts();
    const row0 = opIndex({arr: tableRows0 as any, index: constNumber(0)});
    const img0 = opPick({obj: row0, key: constString('img')});
    const img0ColWithType = await refineNode(client, img0, []);
    expect(defaultLanguageBinding.printType(img0ColWithType.type, false))
      .toEqual(`Tagged<
  tag: Tagged<
    tag: {
      file:File<Table>
    }
    value: {
      table:Maybe<Table>
    }
  >
  value: image-file
>`);

    const table = opTableRowTable({obj: img0ColWithType});
    const tableArtifactVersion = opAssetArtifactVersion({
      asset: table as any,
    });
    expect(await client.query(tableArtifactVersion)).toEqual(AV0_VALUE);
  });

  it('linked table', async () => {
    const client = await testClient();

    const tableRows = getLinkedTable();
    const row0 = opIndex({arr: tableRows as any, index: constNumber(0)});
    const score = opPick({obj: row0, key: constString('score')});
    expect(await client.query(score)).toEqual(14.1);

    const scoreTable = opTableRowTable({obj: score});
    const scoreTableArtifactVersion = opAssetArtifactVersion({
      asset: scoreTable as any,
    });
    expect(await client.query(scoreTableArtifactVersion)).toEqual(AV3_VALUE);

    const linkedStr = opPick({
      obj: row0,
      key: constString('media_row.str'),
    });
    // expect(await CG.execute(context, linkedStr)).toEqual('im-hard-to-find');

    const linkedStrTable = opTableRowTable({obj: linkedStr});
    const linkedStrArtifactVersion = opAssetArtifactVersion({
      asset: linkedStrTable as any,
    });
    expect(await client.query(linkedStrArtifactVersion)).toEqual(
      {id: '3'} // our test server converts the ID to a string :(, but the
      // application behavior is correct
    );
  });

  it('mapped table rows', async () => {
    const client = await testClient();
    const {table0, table1} = getTablesFromDifferentArtifacts();
    const allTableRows = opTableRows({
      table: opArray({0: table0, 1: table1} as any),
    });
    const tableRowsWithType = await refineNode(client, allTableRows, []);

    // Since the two tables have different columns, we get a union
    expect(tableRowsWithType.type).toEqual(
      list(
        union([
          list(
            tableRowValue(
              typedDict({
                img: {
                  boxLayers: {},
                  boxScoreKeys: [],
                  classMap: {},
                  maskLayers: {},
                  type: 'image-file',
                },
                id: 'id',
                str: 'string',
              })
            )
          ),
          list(
            tableRowValue(
              typedDict({
                img: {
                  boxLayers: {},
                  boxScoreKeys: [],
                  classMap: {},
                  maskLayers: {},
                  type: 'image-file',
                },
                id: 'id',
                str: 'string',
                'an-extra-col': 'string',
              })
            )
          ),
        ]),
        2,
        2
      )
    );
  });

  it('mapped table rows with null input', async () => {
    const client = await testClient();
    const {table0, table1, tableNull} = getTablesFromDifferentArtifacts();
    const allTableRows = opTableRows({
      table: opArray({0: table0, 1: table1, 2: tableNull} as any),
    });
    const tableRowsWithType = await refineNode(client, allTableRows, []);

    // Asserting on string representation since the diff is easier to comprehend than
    // when using builder literals.
    expect(defaultLanguageBinding.printType(tableRowsWithType.type, false))
      .toEqual(`List<Union<
  List<Tagged<
    tag: {
      table:Maybe<Tagged<
          tag: {
            file:File<Table>
          }
          value: Maybe<Table>
        >>
    }
    value: {
      img:image-file
      id:id
      str:string
    }
  >> |
  List<Tagged<
    tag: {
      table:Maybe<Tagged<
          tag: {
            file:File<Table>
          }
          value: Maybe<Table>
        >>
    }
    value: {
      img:image-file
      id:id
      str:string
      an-extra-col:string
    }
  >> |
  none
>>`);
  });
});

describe('ancestor behavior', () => {
  it('ancestor assignment', () => {
    const ancestorTaggedType = taggedValue(
      taggedValue(
        taggedValue(typedDict({x: 'string'}), typedDict({z: 'run'})),
        typedDict({y: 'number'})
      ),
      'boolean'
    );
    expect(
      isAssignableTo(
        ancestorTaggedType,
        taggedValue(typedDict({y: 'number'}), 'boolean')
      )
    ).toEqual(true);

    expect(
      isAssignableTo(
        ancestorTaggedType,
        taggedValue(typedDict({z: 'run'}), 'boolean')
      )
    ).toEqual(true);

    expect(
      isAssignableTo(
        ancestorTaggedType,
        taggedValue(typedDict({x: 'string'}), 'boolean')
      )
    ).toEqual(true);
  });

  it('tag getter op', async () => {
    const client = await testClient();

    // Should be able to get direct parent tags
    const runSummary = getFasionSweepRunSummary();
    expect(
      isAssignableTo(runSummary.type, withNamedTag('run', 'run', 'any'))
    ).toEqual(true);
    expect(
      await client.query(opRunInternalId({run: opGetRunTag({obj: runSummary})}))
    ).toEqual(1);

    // Should be able to get ancestor tags
    expect(
      isAssignableTo(runSummary.type, withNamedTag('project', 'project', 'any'))
    ).toEqual(true);
    expect(
      await client.query(
        opProjectInternalId({project: opGetProjectTag({obj: runSummary})})
      )
    ).toEqual(0);

    // Tags are themselves tagged
    const runTag = opGetRunTag({obj: runSummary});
    // sanity check
    expect(
      isAssignableTo(runTag.type, withNamedTag('run', 'run', 'any'))
    ).toEqual(false);
    expect(
      isAssignableTo(runTag.type, withNamedTag('project', 'project', 'any'))
    ).toEqual(true);
    expect(
      await client.query(
        opProjectInternalId({project: opGetProjectTag({obj: runTag})})
      )
    ).toEqual(0);
  });

  it('chained union', () => {
    expect(
      isAssignableTo(
        union([
          taggedValue(
            taggedValue(
              taggedValue(typedDict({a: 'string'}), typedDict({x: 'string'})),
              typedDict({b: 'boolean'})
            ),
            'number'
          ),
          taggedValue(typedDict({a: 'string'}), 'number'),
        ]),
        taggedValue(typedDict({a: 'string'}), 'number')
      )
    ).toEqual(true);
  });
});

describe('opMap tag behavior project.runs.summary.map(r.table)', () => {
  it('type', async () => {
    const client = await testClient();
    const entityName = constString('shawn');
    const projectName = constString('fasion-sweep');
    const fasionSweepRuns = opProjectRuns({
      project: opRootProject({entityName, projectName}),
    });
    const fasionSweepRunsSummary = opRunSummary({run: fasionSweepRuns});
    const pickedTableKey = opPick({
      obj: fasionSweepRunsSummary,
      key: constString('table'),
    });
    const tableKeyType = opIndex({
      arr: pickedTableKey,
      index: varNode('number', 'n'),
    }).type;

    const file0 = opIndex({arr: pickedTableKey, index: constNumber(0)});
    const file0Refined = await refineNode(client, file0, []);
    // This looks good
    expect(file0Refined.type).toEqual({
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
          {
            extension: 'json',
            type: 'file',
            wbObjectType: {columnTypes: {}, type: 'table'},
          },
          'none',
        ],
        type: 'union',
      },
    });

    const tables = opMap({
      arr: pickedTableKey,
      mapFn: constFunction({row: tableKeyType}, ({row}) =>
        opFileTable({file: row})
      ),
    });
    const tableRows = opMap({
      arr: tables,
      mapFn: constFunction({row: tableKeyType}, ({row}) =>
        opTableRows({table: row})
      ),
    });
    const tableRowsRefined = await refineNode(client, tableRows, []);

    // Inlined `TableState.getExampleRow`
    const tableRowsRefinedExample = opIndex({
      arr: tableRowsRefined,
      index: varNode('number', 'n'),
    });
    const tableRowsRefinedExample2 = opIndex({
      arr: tableRowsRefinedExample,
      index: varNode('number', 'n'),
    });

    expect(
      isAssignableTo(
        tableRowsRefinedExample2.type,
        maybe(withNamedTag('run', 'run', 'any'))
      )
    ).toEqual(true);

    const joined = opJoinAll({
      arrs: tableRows as any,
      joinFn: constFunction({row: tableKeyType}, ({row}) =>
        opPick({obj: row, key: constString('a')})
      ) as any,
      outer: constBoolean(false),
    });
    const row0 = opIndex({arr: joined, index: constNumber(0)});
    const pickB = opPick({obj: row0, key: constString('b')});
    const pickBRefined = await refineNode(client, pickB, []);
    // Inlined `TableState.getExampleRow`
    const exampleRow = opIndex({
      arr: pickBRefined,
      index: varNode('number', 'n'),
    });

    expect(
      isAssignableTo(exampleRow.type, maybe(withNamedTag('run', 'run', 'any')))
    ).toEqual(true);
  });
});

describe('findNamedTagInType', () => {
  it('basic', () => {
    expect(
      findNamedTagInType(
        taggedValue(typedDict({a: 'string'}), 'number'),
        'a',
        'string'
      )
    ).toEqual('string');
  });

  it('simple union', () => {
    expect(
      findNamedTagInType(
        union([
          taggedValue(typedDict({a: 'string'}), 'number'),
          taggedValue(typedDict({a: 'string'}), 'none'),
        ]),
        'a',
        'string'
      )
    ).toEqual('string');
  });

  it('union with common tag', () => {
    expect(
      findNamedTagInType(
        union([
          taggedValue(
            typedDict({a: 'string'}),
            taggedValue(typedDict({b: 'boolean'}), 'number')
          ),
          taggedValue(typedDict({a: 'string'}), 'none'),
        ]),
        'a',
        'string'
      )
    ).toEqual('string');
  });

  it('union with missing tag', () => {
    expect(
      findNamedTagInType(
        union([
          taggedValue(
            typedDict({a: 'string'}),
            taggedValue(typedDict({b: 'boolean'}), 'number')
          ),
          taggedValue(typedDict({a: 'string'}), 'none'),
        ]),
        'b',
        'boolean'
      )
    ).toEqual({
      members: [
        'none',
        {
          tag: {propertyTypes: {a: 'string'}, type: 'typedDict'},
          type: 'tagged',
          value: 'boolean',
        },
      ],
      type: 'union',
    });
  });
});
