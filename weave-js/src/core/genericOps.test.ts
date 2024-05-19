import './ops';

import _ from 'lodash';

import * as HL from './hl';
import {defaultLanguageBinding} from './language';
import type {Frame, Node, Type} from './model';
import {
  concreteTaggedValue,
  constBoolean,
  constFunction,
  constNode,
  constNodeUnsafe,
  constNone,
  constNumber,
  constNumberList,
  constString,
  isList,
  list,
  listObjectType,
  maybe,
  taggedValue,
  typedDict,
  union,
  varNode,
  withGroupTag,
} from './model';
import {makeTagGetterOp} from './ops';
import {
  opArray,
  opConcat,
  opCount,
  opDict,
  opGroupby,
  opGroupGroupKey,
  opIndex,
  opJoin,
  opJoinAll,
  opMap,
  opNoneCoalesce,
  opNumberAdd,
  opNumberEqual,
  opNumberGreaterEqual,
  opNumberNotEqual,
  opPick,
  opSort,
} from './ops';
import {testClient} from './testUtil';

const arr1Value = [
  {a: 1, b: 2, c: 3},
  {a: 2, b: 3, c: 3},
  {a: 5, b: 3, c: 3},
];
const arr2Value = [
  {a: 1, b: 2, d: 3},
  {a: 2, b: 3, d: 3},
  {a: 4, b: 3, d: 3},
];
const arr3Value = [
  {a: 1, b: 2, d: 3},
  {a: 2, b: 3, d: 3},
  {a: 4, b: 3, d: 3},
  {a: 4, b: 3, d: 5},
];
const arr1ObjType = typedDict({
  a: 'number' as const,
  b: 'number' as const,
  c: 'number' as const,
});
const arr2ObjType = typedDict({
  a: 'number' as const,
  b: 'number' as const,
  d: 'number' as const,
});
const arr3ObjType = typedDict({
  a: 'number' as const,
  b: 'number' as const,
  d: 'number' as const,
});

const arr1 = constNodeUnsafe(list(arr1ObjType), arr1Value);
const arr3 = constNodeUnsafe(list(arr3ObjType), arr3Value);

function getJoinedTable() {
  return opJoin({
    arr1: constNodeUnsafe(
      {type: 'list', objectType: arr1ObjType},
      arr1Value
    ) as any,
    arr2: constNodeUnsafe(
      {type: 'list', objectType: arr2ObjType},
      arr2Value
    ) as any,
    join1Fn: constFunction({row: arr1ObjType}, ({row}) =>
      opPick({obj: row, key: constString('a')})
    ) as any,
    join2Fn: constFunction({row: arr2ObjType}, ({row}) =>
      opPick({obj: row, key: constString('a')})
    ) as any,
    alias1: constString('arr1'),
    alias2: constString('arr2'),
    leftOuter: constBoolean(true),
    rightOuter: constBoolean(true),
  });
}

function getJoinedToTaggedNoneTable() {
  return opJoin({
    arr1: constNodeUnsafe(
      {type: 'list', objectType: arr1ObjType},
      arr1Value
    ) as any,
    arr2: constNodeUnsafe(
      maybe(list(arr2ObjType)),
      concreteTaggedValue('a_string', undefined)
    ) as any,
    join1Fn: constFunction({row: arr1ObjType}, ({row}) =>
      opPick({obj: row, key: constString('a')})
    ) as any,
    join2Fn: constFunction({row: arr2ObjType}, ({row}) =>
      opPick({obj: row, key: constString('a')})
    ) as any,
    alias1: constString('arr1'),
    alias2: constString('arr2'),
    leftOuter: constBoolean(true),
    rightOuter: constBoolean(true),
  });
}

const simpleTableData = [
  {a: 1, b: 3, c: 2},
  {a: 2, b: 1, c: 2},
  {a: 3, b: 2, c: 2},
  {a: 4, b: 3, c: 1},
  {a: 5, b: 1, c: 1},
  {a: 6, b: 2, c: 1},
  {a: 7, b: 3, c: 3},
  {a: 8, b: 1, c: 3},
  {a: 9, b: 2, c: 3},
];
function getSimpleTable() {
  return constNodeUnsafe(
    {
      type: 'list',
      objectType: typedDict({
        a: 'number' as const,
        b: 'number' as const,
        c: 'number' as const,
      }),
    },
    simpleTableData
  );
}

function getComparableDataFn(keys: string[], inputTableNode: Node) {
  const exampleRowNode = opIndex({
    arr: inputTableNode as any,
    index: varNode('number', 'n'),
  });

  const vals: Frame = {};
  for (const key of keys) {
    const inputVale: Node = varNode(exampleRowNode.type, 'row');
    const colSelectFunction = opPick({
      obj: inputVale,
      key: constNodeUnsafe('string', key),
    });
    vals[key] = colSelectFunction;
  }
  return opArray(vals as any);
}
async function assertTableSort(
  table: Node,
  rawData: any[],
  keys: string[],
  dirs: Array<'asc' | 'desc'>
) {
  const client = await testClient();
  const compFn = getComparableDataFn(keys, table);
  const compFnConst = constNodeUnsafe(compFn.type, compFn);
  const columnDirsConst = constNodeUnsafe(
    {type: 'list', objectType: 'string'},
    dirs
  );
  const sortedTable = opSort({
    arr: table as any,
    compFn: compFnConst as any,
    columnDirs: columnDirsConst,
  });
  expect(await client.query(sortedTable)).toEqual(
    _.orderBy(rawData, keys, dirs)
  );
}

function getDoubleJoinedTable() {
  const joinedTable1 = getJoinedTable();
  const joinedTable2 = getJoinedTable();

  return opJoin({
    arr1: joinedTable1 as any,
    arr2: joinedTable2 as any,
    join1Fn: constFunction({row: listObjectType(joinedTable1.type)}, ({row}) =>
      opPick({obj: row, key: constString('arr1.a')})
    ) as any,
    join2Fn: constFunction({row: listObjectType(joinedTable2.type)}, ({row}) =>
      opPick({obj: row, key: constString('arr2.a')})
    ) as any,
    alias1: constString('0'),
    alias2: constString('1'),
    leftOuter: constBoolean(true),
    rightOuter: constBoolean(true),
  });
}

function getNestedObject() {
  const obj = {a: 1, b: 2, c: 3, e: {x: 'a'}};
  const objType: Type = {
    type: 'typedDict' as const,
    propertyTypes: {
      a: 'number' as const,
      b: 'number' as const,
      c: 'number' as const,
      e: {
        type: 'union' as const,
        members: [
          'none',
          {
            type: 'typedDict' as const,
            propertyTypes: {
              x: 'string' as const,
            },
          },
        ],
      },
    },
  };
  return constNodeUnsafe(objType as any, obj);
}

function getComplicatedArray() {
  const arr = [
    {
      arr1: {a: 1, b: 2, c: 3, e: {x: 'a'}},
      arr2: {a: 1, b: 2, d: 3},
      arr3: [
        {inner: [{b: 1}, {b: 2}]},
        {inner: [{b: 3}, {b: 4}]},
        {inner: []},
        {},
      ],
    },
    {arr1: {a: 2, b: 3, c: 3, e: {x: 'b'}}, arr2: {a: 2, b: 3, d: 3}},
    {arr1: {a: 5, b: 3, c: 3}, arr2: null},
    {arr1: null, arr2: {a: 4, b: 3, d: 3}},
  ];
  const arrType: Type = {
    type: 'list' as const,
    objectType: {
      type: 'typedDict' as const,
      propertyTypes: {
        arr1: {
          type: 'union' as const,
          members: [
            'none',
            {
              type: 'typedDict' as const,
              propertyTypes: {
                a: 'number' as const,
                b: 'number' as const,
                c: 'number' as const,
                e: {
                  type: 'union' as const,
                  members: [
                    'none',
                    {
                      type: 'typedDict' as const,
                      propertyTypes: {
                        x: 'string' as const,
                      },
                    },
                  ],
                },
              },
            },
          ],
        },
        arr2: {
          type: 'union' as const,
          members: [
            'none',
            {
              type: 'typedDict' as const,
              propertyTypes: {
                a: 'number' as const,
                b: 'string' as const,
                d: 'number' as const,
              },
            },
          ],
        },
        arr3: {
          type: 'union' as const,
          members: [
            'none',
            {
              type: 'list',
              objectType: {
                type: 'union' as const,
                members: [
                  'none',
                  {
                    type: 'typedDict' as const,
                    propertyTypes: {
                      inner: {
                        type: 'union' as const,
                        members: [
                          'none',
                          {
                            type: 'list',
                            objectType: {
                              type: 'union' as const,
                              members: [
                                'none',
                                {
                                  type: 'typedDict',
                                  propertyTypes: {
                                    b: 'number',
                                  },
                                },
                              ],
                            },
                          },
                        ],
                      },
                    },
                  },
                ],
              },
            },
          ],
        },
      },
    },
  };
  return constNodeUnsafe(arrType as any, arr);
}

function getPickedArrayObjType(type: Type) {
  if (!isList(type)) {
    throw new Error('invalid');
  }
  return type.objectType;
}

describe('generic ops', () => {
  it('join', async () => {
    const client = await testClient();
    const joined = getJoinedTable();
    expect(joined.type).toEqual({
      objectType: {
        tag: {
          propertyTypes: {
            joinKey: 'string',
            joinObj: {
              members: ['none', 'number'],
              type: 'union',
            },
          },
          type: 'typedDict',
        },
        type: 'tagged',
        value: {
          propertyTypes: {
            arr1: {
              members: ['none', arr1ObjType],
              type: 'union',
            },
            arr2: {
              members: ['none', arr2ObjType],
              type: 'union',
            },
          },
          type: 'typedDict',
        },
      },
      type: 'list',
    });
    expect(await client.query(joined)).toEqual([
      {arr1: {a: 1, b: 2, c: 3}, arr2: {a: 1, b: 2, d: 3}},
      {arr1: {a: 2, b: 3, c: 3}, arr2: {a: 2, b: 3, d: 3}},
      {arr1: {a: 5, b: 3, c: 3}, arr2: null},
      {arr1: null, arr2: {a: 4, b: 3, d: 3}},
    ]);
  });

  it('join to tagged none', async () => {
    const client = await testClient();
    const joined = getJoinedToTaggedNoneTable();
    expect(joined.type).toEqual({
      objectType: {
        tag: {
          propertyTypes: {
            joinKey: 'string',
            joinObj: {
              members: ['none', 'number'],
              type: 'union',
            },
          },
          type: 'typedDict',
        },
        type: 'tagged',
        value: {
          propertyTypes: {
            arr1: {
              members: ['none', arr1ObjType],
              type: 'union',
            },
            arr2: {
              members: ['none', arr2ObjType],
              type: 'union',
            },
          },
          type: 'typedDict',
        },
      },
      type: 'list',
    });
    expect(await client.query(joined)).toEqual([
      {arr1: {a: 1, b: 2, c: 3}, arr2: null},
      {arr1: {a: 2, b: 3, c: 3}, arr2: null},
      {arr1: {a: 5, b: 3, c: 3}, arr2: null},
    ]);
  });

  it('double join', async () => {
    const client = await testClient();
    const joined = getDoubleJoinedTable();
    expect(joined.type).toEqual({
      objectType: {
        tag: {
          propertyTypes: {
            joinKey: 'string',
            joinObj: {
              members: [
                'none',
                {
                  tag: {
                    propertyTypes: {
                      joinKey: 'string',
                      joinObj: {
                        members: ['none', 'number'],
                        type: 'union',
                      },
                    },
                    type: 'typedDict',
                  },
                  type: 'tagged',
                  value: {
                    members: ['none', 'number'],
                    type: 'union',
                  },
                },
              ],
              type: 'union',
            },
          },
          type: 'typedDict',
        },
        type: 'tagged',
        value: {
          propertyTypes: {
            '0': {
              members: [
                'none',
                {
                  tag: {
                    propertyTypes: {
                      joinKey: 'string',
                      joinObj: {
                        members: ['none', 'number'],
                        type: 'union',
                      },
                    },
                    type: 'typedDict',
                  },
                  type: 'tagged',
                  value: {
                    propertyTypes: {
                      arr1: {
                        members: ['none', arr1ObjType],
                        type: 'union',
                      },
                      arr2: {
                        members: ['none', arr2ObjType],
                        type: 'union',
                      },
                    },
                    type: 'typedDict',
                  },
                },
              ],
              type: 'union',
            },
            '1': {
              members: [
                'none',
                {
                  tag: {
                    propertyTypes: {
                      joinKey: 'string',
                      joinObj: {
                        members: ['none', 'number'],
                        type: 'union',
                      },
                    },
                    type: 'typedDict',
                  },
                  type: 'tagged',
                  value: {
                    propertyTypes: {
                      arr1: {
                        members: ['none', arr1ObjType],
                        type: 'union',
                      },
                      arr2: {
                        members: ['none', arr2ObjType],
                        type: 'union',
                      },
                    },
                    type: 'typedDict',
                  },
                },
              ],
              type: 'union',
            },
          },
          type: 'typedDict',
        },
      },
      type: 'list',
    });

    expect(await client.query(joined)).toEqual([
      {
        '0': {arr1: {a: 1, b: 2, c: 3}, arr2: {a: 1, b: 2, d: 3}},
        '1': {arr1: {a: 1, b: 2, c: 3}, arr2: {a: 1, b: 2, d: 3}},
      },
      {
        '0': {arr1: {a: 2, b: 3, c: 3}, arr2: {a: 2, b: 3, d: 3}},
        '1': {arr1: {a: 2, b: 3, c: 3}, arr2: {a: 2, b: 3, d: 3}},
      },
      {'0': {arr1: {a: 5, b: 3, c: 3}, arr2: null}, '1': null},
      {
        '0': {arr1: null, arr2: {a: 4, b: 3, d: 3}},
        '1': {arr1: {a: 5, b: 3, c: 3}, arr2: null},
      },
      {'0': null, '1': {arr1: null, arr2: {a: 4, b: 3, d: 3}}},
    ]);
  });

  it('pick from joined', async () => {
    const client = await testClient();
    const joined = getJoinedTable();
    let picked = opPick({obj: joined, key: constString('arr1.a')});
    let pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(
      defaultLanguageBinding.printType(
        getPickedArrayObjType(pickedWithType.type),
        false
      )
    ).toEqual(`Tagged<
  tag: {
    joinKey:string
    joinObj:Maybe<number>
  }
  value: Maybe<number>
>`);
    expect(await client.query(picked)).toEqual([1, 2, 5, null]);

    // Picking an invalid nested value results in null
    picked = opPick({obj: joined, key: constString('arr1.d')});
    pickedWithType = await HL.refineNode(client, picked, []);
    expect(defaultLanguageBinding.printType(pickedWithType.type)).toEqual(
      'List<none>'
    );
    expect(await client.query(picked)).toEqual([null, null, null, null]);
  });

  it('pick from double-joined', async () => {
    const client = await testClient();
    const joined = getDoubleJoinedTable();
    let picked = opPick({obj: joined, key: constString('0.arr1.b')});
    let pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(
      defaultLanguageBinding.printType(
        getPickedArrayObjType(pickedWithType.type),
        false
      )
    ).toEqual(`Union<
  Tagged<
    tag: {
      joinKey:string
      joinObj:Maybe<Tagged<
          tag: {
            joinKey:string
            joinObj:Maybe<number>
          }
          value: Maybe<number>
        >>
    }
    value: none
  > |
  Tagged<
    tag: Tagged<
      tag: {
        joinKey:string
        joinObj:Maybe<Tagged<
            tag: {
              joinKey:string
              joinObj:Maybe<number>
            }
            value: Maybe<number>
          >>
      }
      value: {
        joinKey:string
        joinObj:Maybe<number>
      }
    >
    value: Maybe<number>
  >
>`);
    expect(await client.query(picked)).toEqual([2, 3, 3, null, null]);

    // Picking an invalid nested value results in null
    picked = opPick({obj: joined, key: constString('1.arr1.d')});
    pickedWithType = await HL.refineNode(client, picked, []);
    expect(defaultLanguageBinding.printType(pickedWithType.type, false))
      .toEqual(`List<Union<
  Tagged<
    tag: {
      joinKey:string
      joinObj:Maybe<Tagged<
          tag: {
            joinKey:string
            joinObj:Maybe<number>
          }
          value: Maybe<number>
        >>
    }
    value: none
  > |
  Tagged<
    tag: Tagged<
      tag: {
        joinKey:string
        joinObj:Maybe<Tagged<
            tag: {
              joinKey:string
              joinObj:Maybe<number>
            }
            value: Maybe<number>
          >>
      }
      value: {
        joinKey:string
        joinObj:Maybe<number>
      }
    >
    value: none
  >
>>`);
    expect(await client.query(picked)).toEqual([null, null, null, null, null]);
  });

  it('pick a', async () => {
    const client = await testClient();
    const objNode = getNestedObject();
    const picked = opPick({
      obj: objNode as any,
      key: constString('a'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(defaultLanguageBinding.printType(pickedWithType.type)).toEqual(
      'number'
    );
    expect(await client.query(picked)).toEqual(1);
  });

  it('pick *.a', async () => {
    const client = await testClient();
    const arrNode = getComplicatedArray();

    const picked = opPick({
      obj: arrNode as any,
      key: constString('*.a'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(defaultLanguageBinding.printType(pickedWithType.type, false))
      .toEqual(`List<{
  arr1:Maybe<number>
  arr2:Maybe<number>
  arr3:none
}>`);
    expect(await client.query(picked)).toEqual([
      {arr1: 1, arr2: 1, arr3: null},
      {arr1: 2, arr2: 2},
      {arr1: 5, arr2: null},
      {arr1: null, arr2: 4},
    ]);
  });

  it('pick through array and objects arr3.*.inner.*.b', async () => {
    const client = await testClient();
    const arrNode = getComplicatedArray();

    const picked = opPick({
      obj: arrNode as any,
      key: constString('arr3.*.inner.*.b'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(
      defaultLanguageBinding.printType(pickedWithType.type, false)
    ).toEqual(`List<Maybe<List<Maybe<List<Maybe<number>>>>>>`);
    expect(await client.query(picked)).toEqual([
      [[1, 2], [3, 4], [], null],
      null,
      null,
      null,
    ]);
  });

  it('pick arr1', async () => {
    const client = await testClient();
    const arrNode = getComplicatedArray();

    const picked = opPick({
      obj: arrNode as any,
      key: constString('arr1'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(
      defaultLanguageBinding.printType(
        getPickedArrayObjType(pickedWithType.type),
        false
      )
    ).toEqual(`Maybe<{
    a:number
    b:number
    c:number
    e:Maybe<{
        x:string
      }>
  }>`);
    expect(await client.query(picked)).toEqual([
      {a: 1, b: 2, c: 3, e: {x: 'a'}},
      {a: 2, b: 3, c: 3, e: {x: 'b'}},
      {a: 5, b: 3, c: 3},
      null,
    ]);
  });

  it('pick *.d', async () => {
    const client = await testClient();
    const arrNode = getComplicatedArray();

    const picked = opPick({
      obj: arrNode as any,
      key: constString('*.d'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(defaultLanguageBinding.printType(pickedWithType.type, false))
      .toEqual(`List<{
  arr1:none
  arr2:Maybe<number>
  arr3:none
}>`);
    expect(await client.query(picked)).toEqual([
      {arr1: null, arr2: 3, arr3: null},
      {arr1: null, arr2: 3},
      {arr1: null, arr2: null},
      {arr1: null, arr2: 3},
    ]);
  });
  it('pick *.*.x', async () => {
    const client = await testClient();
    const arrNode = getComplicatedArray();

    const picked = opPick({
      obj: arrNode as any,
      key: constString('*.*.x'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(defaultLanguageBinding.printType(pickedWithType.type, false))
      .toEqual(`List<{
  arr1:Maybe<{
      a:none
      b:none
      c:none
      e:Maybe<string>
    }>
  arr2:Maybe<{
      a:none
      b:none
      d:none
    }>
  arr3:Maybe<List<none>>
}>`);
    expect(await client.query(picked)).toEqual([
      {
        arr1: {a: null, b: null, c: null, e: 'a'},
        arr2: {a: null, b: null, d: null},
        arr3: [null, null, null, null],
      },
      {
        arr1: {a: null, b: null, c: null, e: 'b'},
        arr2: {a: null, b: null, d: null},
      },
      {arr1: {a: null, b: null, c: null}, arr2: null},
      {arr1: null, arr2: {a: null, b: null, d: null}},
    ]);
  });

  it('pick *.e.x', async () => {
    const client = await testClient();
    const arrNode = getComplicatedArray();

    const picked = opPick({
      obj: arrNode as any,
      key: constString('*.e.x'),
    });
    const pickedWithType = await HL.refineNode(client, picked, []);

    // Can pick a nested value and get a nullable type
    expect(defaultLanguageBinding.printType(pickedWithType.type, false))
      .toEqual(`List<{
  arr1:Maybe<string>
  arr2:none
  arr3:none
}>`);
    expect(await client.query(picked)).toEqual([
      {arr1: 'a', arr2: null, arr3: null},
      {arr1: 'b', arr2: null},
      {arr1: null, arr2: null},
      {arr1: null, arr2: null},
    ]);
  });

  it('ops can be projected', async () => {
    const client = await testClient();
    let arrNumbers = constNodeUnsafe(list('number'), [1, 2]);
    expect(
      HL.availableOpsForChain(arrNumbers, client.opStore).map(o => o.name)
    ).toEqual([
      'numbers-sum',
      'numbers-avg',
      'numbers-argmax',
      'numbers-argmin',
      'numbers-stddev',
      'numbers-min',
      'numbers-max',
      'number-add',
      'number-sub',
      'number-mult',
      'number-div',
      'number-floorDiv',
      'number-modulo',
      'number-powBinary',
      'number-equal',
      'number-notEqual',
      'number-less',
      'number-greater',
      'number-lessEqual',
      'number-greaterEqual',
      'number-toString',
      'number-abs',
      'number-sin',
      'number-cos',
      'number-toTimestamp',
      'number-negate',
      'isNone',
      'count',
      'joinToStr',
      'index',
      'filter',
      'dropna',
      'map',
      'join',
      'contains',
    ]);
    let added = opNumberAdd({lhs: arrNumbers, rhs: constNumber(1)});
    expect(added.type).toEqual(list('number'));
    expect(await client.query(added)).toEqual([2, 3]);

    arrNumbers = constNodeUnsafe(list(union(['none', 'number'])), [1, 2, null]);
    added = opNumberAdd({lhs: arrNumbers, rhs: constNumber(1)});
    expect(added.type).toEqual(list(union(['none', 'number'])));
    expect(await client.query(added)).toEqual([2, 3, null]);
  });

  it('add to tagged value', async () => {
    const client = await testClient();
    const num1 = {_tag: 'x', _value: 1};
    const num2 = {_tag: 'y', _value: 2};
    const tv = constNodeUnsafe(list(taggedValue('string', 'number')), [
      num1,
      num2,
    ]);
    const added = opNumberAdd({lhs: tv, rhs: constNumber(1)});
    expect(await client.query(added)).toEqual([2, 3]);
  });

  it('pick tagged value', async () => {
    const client = await testClient();

    let tv = constNodeUnsafe(
      taggedValue('string', typedDict({a: 'number', b: 'number'})),
      {_tag: 'x', _value: {a: 1, b: 2}}
    );
    let picked = opPick({obj: tv as any, key: constString('b')});
    let pickedWithType = await HL.refineNode(client, picked, []);
    expect(pickedWithType.type).toEqual({
      tag: 'string',
      type: 'tagged',
      value: 'number',
    });
    expect(await client.query(picked)).toEqual(2);

    tv = constNodeUnsafe(
      list(taggedValue('string', typedDict({a: 'number', b: 'number'}))),
      [
        {_tag: 'y', _value: {a: 99, b: 98}},
        {_tag: 'x', _value: {a: 1, b: 2}},
      ]
    );
    picked = opPick({obj: tv as any, key: constString('b')});
    pickedWithType = await HL.refineNode(client, picked, []);
    expect(
      defaultLanguageBinding.printType(
        getPickedArrayObjType(pickedWithType.type),
        false
      )
    ).toEqual(`Tagged<
  tag: string
  value: number
>`);
    expect(await client.query(picked)).toEqual([98, 2]);
  });

  it('ops are null chainable', async () => {});

  it('group by and tagged value', async () => {
    const client = await testClient();
    const grouped: Node = opGroupby({
      arr: arr1 as any,
      groupByFn: constFunction({row: arr1ObjType}, ({row}) =>
        opNumberAdd({
          lhs: opPick({obj: row, key: constString('b')}),
          rhs: constNumber(1),
        })
      ) as any,
    });
    expect(grouped.type).toEqual(
      list(withGroupTag(list(arr1ObjType), 'number'))
    );
    const row1 = opIndex({arr: grouped as any, index: constNumber(1)});
    const picked = opPick({obj: row1 as any, key: constString('a')});
    expect(await client.query(picked)).toEqual([2, 5]);
  });
  it('group by greater than', async () => {
    const client = await testClient();
    const grouped: Node = opGroupby({
      arr: arr1 as any,
      groupByFn: constFunction({row: arr1ObjType}, ({row}) =>
        opNumberGreaterEqual({
          lhs: opPick({
            obj: row,
            key: constString('b'),
          }) as any,
          rhs: constNumber(2),
        })
      ) as any,
    });
    expect(grouped.type).toEqual(
      list(withGroupTag(list(arr1ObjType), 'boolean'))
    );
    const row1 = opIndex({arr: grouped as any, index: constNumber(0)});
    const picked = opPick({obj: row1 as any, key: constString('a')});
    await HL.refineNode(client, picked, []);
    expect(await client.query(picked)).toEqual([1, 2, 5]);
    const tag = opGroupGroupKey({obj: row1 as any});
    await HL.refineNode(client, tag, []);
    expect(await client.query(tag)).toEqual(true);
  });

  it('group by multiple, aggregate, get group table', async () => {
    const client = await testClient();
    // Group by multiple keys by grouping by a dictionary
    let grouped1 = opGroupby({
      arr: arr1 as any,
      groupByFn: constFunction(
        {row: arr1ObjType},
        ({row}) =>
          opDict({
            a: opPick({
              obj: row,
              key: constString('a'),
            }),
            b: opPick({
              obj: row,
              key: constString('b'),
            }),
          } as any) as any
      ),
    });
    grouped1 = (await HL.refineNode(client, grouped1, [])) as any;
    expect(defaultLanguageBinding.printType(grouped1.type, false))
      .toEqual(`List<Tagged<
  tag: {
    groupKey:{
      a:number
      b:number
    }
  }
  value: List<{
    a:number
    b:number
    c:number
  }>
>>`);
    const groupedExample = opIndex({
      arr: grouped1 as any,
      index: varNode('number', 'n'),
    });

    // Count each group by mapping, also return group key
    const counted = opMap({
      arr: grouped1 as any,
      mapFn: constFunction(
        {row: groupedExample.type},
        ({row}) =>
          opDict({
            key: opGroupGroupKey({obj: row}),
            val: opCount({
              arr: row,
            }) as any,
          } as any) as any
      ) as any,
    });
    expect(defaultLanguageBinding.printType(counted.type, false))
      .toEqual(`List<{
  key:{
    a:number
    b:number
  }
  val:Tagged<
    tag: {
      groupKey:{
        a:number
        b:number
      }
    }
    value: number
  >
}>`);
    expect(await client.query(counted)).toEqual([
      {key: {a: 1, b: 2}, val: 1},
      {key: {a: 2, b: 3}, val: 1},
      {key: {a: 5, b: 3}, val: 1},
    ]);
  });

  it('group by multiple, aggregate, get group table, more than one row per group', async () => {
    const client = await testClient();
    // Group by multiple keys by grouping by a dictionary
    let grouped1 = opGroupby({
      arr: arr3 as any,
      groupByFn: constFunction(
        {row: arr1ObjType},
        ({row}) =>
          opDict({
            a: opPick({
              obj: row,
              key: constString('a'),
            }),
            b: opPick({
              obj: row,
              key: constString('b'),
            }),
          } as any) as any
      ),
    });
    grouped1 = (await HL.refineNode(client, grouped1, [])) as any;
    expect(defaultLanguageBinding.printType(grouped1.type, false))
      .toEqual(`List<Tagged<
  tag: {
    groupKey:{
      a:number
      b:number
    }
  }
  value: List<{
    a:number
    b:number
    d:number
  }>
>>`);

    const result = await client.query(grouped1);
    expect(result).toEqual([
      [{a: 1, b: 2, d: 3}],
      [{a: 2, b: 3, d: 3}],
      [
        {a: 4, b: 3, d: 3},
        {a: 4, b: 3, d: 5},
      ],
    ]);
  });

  it('simple sort', async () => {
    const table = getSimpleTable();
    assertTableSort(table, simpleTableData, ['a'], ['asc']);
    assertTableSort(table, simpleTableData, ['a'], ['desc']);
    assertTableSort(table, simpleTableData, ['c', 'b'], ['asc', 'asc']);
    assertTableSort(table, simpleTableData, ['c', 'b'], ['desc', 'asc']);
    assertTableSort(table, simpleTableData, ['c', 'b'], ['asc', 'desc']);
    assertTableSort(table, simpleTableData, ['c', 'b'], ['desc', 'desc']);
  });

  it('opTypes: op number add', async () => {
    // This test verifies generic behavior of opTypes mappableNullableTaggable*
    // TODO: test tag behavior

    const client = await testClient();

    // number, number
    let res = opNumberAdd({lhs: constNumber(5), rhs: constNumber(6)});
    expect(res.type).toEqual('number');
    expect(await client.query(res)).toEqual(11);

    // number[], number
    res = opNumberAdd({
      lhs: constNumberList([5, 6, 7]),
      rhs: constNumber(6),
    });
    expect(res.type).toEqual(list('number'));
    expect(await client.query(res)).toEqual([11, 12, 13]);

    // null, number
    res = opNumberAdd({
      lhs: constNone(),
      rhs: constNumber(6),
    });
    expect(res.type).toEqual('none');
    expect(await client.query(res)).toEqual(null);

    // number, null
    res = opNumberAdd({
      lhs: constNumber(9),
      rhs: constNone(),
    });
    expect(res.type).toEqual('none');
    expect(await client.query(res)).toEqual(null);

    // (number | null)[], number
    res = opNumberAdd({
      lhs: opArray({0: constNumber(5), 1: constNone()} as any),
      rhs: constNumber(6),
    });
    expect(res.type).toEqual(list(maybe('number'), 2, 2));
    expect(await client.query(res)).toEqual([11, null]);

    // (number | null)[], null
    res = opNumberAdd({
      lhs: opArray({0: constNumber(5), 1: constNone()} as any),
      rhs: constNone(),
    });
    expect(res.type).toEqual(list('none', 2, 2));
    expect(await client.query(res)).toEqual([null, null]);
  });

  it('opTypes: op concat', async () => {
    const client = await testClient();

    // simple concat
    let res = opConcat({
      arr: constNode<Type>(
        list({
          type: 'list' as const,
          objectType: 'number' as const,
        }),
        [[1], [2, 3]]
      ) as any,
    });
    expect(res.type).toEqual(list('number'));
    expect(await client.query(res)).toEqual([1, 2, 3]);

    // simple concat with null and mixed
    res = opConcat({
      arr: constNode<Type>(
        {
          type: 'list' as const,
          objectType: {
            type: 'union' as const,
            members: [
              {type: 'list' as const, objectType: 'number' as const},
              {
                type: 'list' as const,
                objectType: maybe('number' as const),
              },
              'none' as const,
              {
                type: 'list' as const,
                objectType: {
                  type: 'typedDict' as const,
                  propertyTypes: {
                    a: 'string',
                    b: 'number',
                  },
                },
              },
            ],
          },
        },
        [
          [1],
          [2, 3],
          null,
          [{a: 'a', b: 1} as any],
          [1, null],
          [{a: 'b', b: 2} as any],
        ]
      ) as any,
    });
    expect(res.type).toEqual(
      list({
        type: 'union' as const,
        members: [
          'number' as const,
          'none',
          {
            type: 'typedDict' as const,
            propertyTypes: {
              a: 'string',
              b: 'number',
            },
          },
        ],
      })
    );
    expect(await client.query(res)).toEqual([
      1,
      2,
      3,
      {a: 'a', b: 1} as any,
      1,
      null,
      {a: 'b', b: 2} as any,
    ]);

    // Tagged<List<Tagged<List<Tagged<number>>>>>
    res = opConcat({
      arr: constNode<Type>(
        taggedValue(
          typedDict({tag: 'string'}),
          list(
            taggedValue(
              typedDict({tag2: 'string'}),
              list(taggedValue(typedDict({tag3: 'string'}), 'number'))
            )
          )
        ),
        concreteTaggedValue({tag: 'value'}, [
          concreteTaggedValue({tag2: 'v21'}, [
            concreteTaggedValue({tag3: 'v31'}, 1),
          ]),
          concreteTaggedValue({tag2: 'v22'}, [
            concreteTaggedValue({tag3: 'v32'}, 2),
            concreteTaggedValue({tag3: 'v33'}, 3),
          ]),
        ])
      ) as any,
    });
    expect(res.type).toEqual(
      taggedValue(
        typedDict({tag: 'string'}),
        list(
          taggedValue(
            taggedValue(
              typedDict({tag2: 'string'}),
              typedDict({tag3: 'string'})
            ),
            'number'
          )
        )
      )
    );
    // We can't query for tags directly anymore.
    // expect(await client.query(res, {}, false)).toEqual(
    //   TypeHelpers.concreteTaggedValue({tag: 'value'}, [
    //     TypeHelpers.concreteTaggedValue(
    //       TypeHelpers.concreteTaggedValue({tag2: 'v21'}, {tag3: 'v31'}),
    //       1
    //     ),
    //     TypeHelpers.concreteTaggedValue(
    //       TypeHelpers.concreteTaggedValue({tag2: 'v22'}, {tag3: 'v32'}),
    //       2
    //     ),
    //     TypeHelpers.concreteTaggedValue(
    //       TypeHelpers.concreteTaggedValue({tag2: 'v22'}, {tag3: 'v33'}),
    //       3
    //     ),
    //   ])
    // );
  });
});

describe('equality ops', () => {
  it('1 = None', async () => {
    expect(
      await (
        await testClient()
      ).query(opNumberEqual({lhs: constNumber(1), rhs: constNone()}))
    ).toEqual(false);
  });
  it('None = None', async () => {
    expect(
      await (
        await testClient()
      ).query(opNumberEqual({lhs: constNone(), rhs: constNone()}))
    ).toEqual(true);
  });
  it('None = 1', async () => {
    expect(
      await (
        await testClient()
      ).query(opNumberEqual({lhs: constNone(), rhs: constNumber(1)}))
    ).toEqual(false);
  });
  it('1 = 1', async () => {
    expect(
      await (
        await testClient()
      ).query(opNumberEqual({lhs: constNumber(1), rhs: constNumber(1)}))
    ).toEqual(true);
  });
  it('0 = 1', async () => {
    expect(
      await (
        await testClient()
      ).query(opNumberEqual({lhs: constNumber(0), rhs: constNumber(1)}))
    ).toEqual(false);
  });

  it('[None, 0, 1] = 0', async () => {
    expect(
      await (
        await testClient()
      ).query(
        opNumberEqual({
          lhs: constNodeUnsafe(list(maybe('number')), [null, 0, 1]),
          rhs: constNumber(0),
        })
      )
    ).toEqual([false, true, false]);
  });

  it('[None, 0, 1] = 0', async () => {
    expect(
      await (
        await testClient()
      ).query(
        opNumberEqual({
          lhs: constNodeUnsafe(list(maybe('number')), [null, 0, 1]),
          rhs: constNone(),
        })
      )
    ).toEqual([true, false, false]);
  });

  it('coalesce a', async () => {
    // Evaluates all 81 combinations
    /*
    type options: CS, NS, CLC, CLN, NLC, NLN
    nullable? (nullable is either none or maybe)
      |-Y- listlike?
      |       |-Y- listObjIsNullable?
      |       |         |-Y-------- NLN
      |       |         |-N-------- NLC
      |       |
      |       |-N------------------ NS
      |
      |-N- listlike?
              |-Y- listObjIsNullable?
              |         |-Y-------- CLN
              |         |
              |         |-N-------- CLC
              |
              |-N------------------ CS

                    RHS
                  CS | NS
              CS    lhs
              NS    union<nonnull<lhs>, rhs>
      LHS     CLC   lhs
              CLN   list<union<nonnull<lhs.objtype>, rhs>>
              NLC   union<nonnull<lhs>, rhs>
              NLN   union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, rhs>>>

                     RHS
                  CLC | CLN
              CS    lhs
              NS    union<nonnull<lhs>, rhs>
      LHS     CLC   lhs
              CLN   list<union<nonnull<lhs.objtype>, rhs.objtype>>
              NLC   union<nonnull<lhs>, rhs>
              NLN   union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, rhs.objtype>>>

                      RHS
                  NLC | NLN
              CS    lhs
              NS    union<nonnull<lhs>, rhs>
      LHS     CLC   lhs
              CLN   union<lhs, list<union<lhs.objtype, rhs.objtype>>>
              NLC   union<nonnull<lhs>, rhs>
              NLN   union<rhs, list<union<nonnull<nonnull<lhs>.objtype>, nonnull<rhs>.objtype>>>
    */

    const client = await testClient();

    const CSNumber = constNumber(1);
    const NSNumberC = constNodeUnsafe(maybe('number'), 1);
    const NSNumberN = constNodeUnsafe(maybe('number'), null);
    const CLCNumber = constNodeUnsafe(list('number'), [1, 2, 3, 4]);
    const CLNNumber = constNodeUnsafe(list(maybe('number')), [
      1,
      null,
      3,
      null,
    ]);
    const NLCNumberC = constNodeUnsafe(maybe(list('number')), [1, 2, 3, 4]);
    const NLCNumberN = constNodeUnsafe(maybe(list('number')), null);
    const NLNNumberC = constNodeUnsafe(maybe(list(maybe('number'))), [
      1,
      null,
      3,
      null,
    ]);
    const NLNNumberN = constNodeUnsafe(maybe(list(maybe('number'))), null);

    const CSString = constString('a');
    const NSStringC = constNodeUnsafe(maybe('string'), 'a');
    const NSStringN = constNodeUnsafe(maybe('string'), null);
    const CLCString = constNodeUnsafe(list('string'), ['a', 'b', 'c', 'd']);
    const CLNString = constNodeUnsafe(list(maybe('string')), [
      'a',
      'b',
      null,
      null,
    ]);
    const NLCStringC = constNodeUnsafe(maybe(list('string')), [
      'a',
      'b',
      'c',
      'd',
    ]);
    const NLCStringN = constNodeUnsafe(maybe(list('string')), null);
    const NLNStringC = constNodeUnsafe(maybe(list(maybe('string'))), [
      'a',
      'b',
      null,
      null,
    ]);
    const NLNStringN = constNodeUnsafe(maybe(list(maybe('string'))), null);

    const rhsAll = [
      CSString,
      NSStringC,
      NSStringN,
      CLCString,
      CLNString,
      NLCStringC,
      NLCStringN,
      NLNStringC,
      NLNStringN,
    ];

    let node;

    // LHS = CS
    for (const rhsNdx in rhsAll) {
      if (rhsAll[rhsNdx] !== undefined) {
        const rhs = rhsAll[rhsNdx];
        node = opNoneCoalesce({lhs: CSNumber, rhs: rhs as any});
        expect(node.type).toEqual('number');
        expect(await client.query(node)).toEqual(1);
      }
    }

    // LHS = NS_c
    for (const rhsNdx in rhsAll) {
      if (rhsAll[rhsNdx] !== undefined) {
        const rhs = rhsAll[rhsNdx];
        node = opNoneCoalesce({lhs: NSNumberC, rhs: rhs as any});
        expect(node.type).toEqual(union(['number', rhs.type]));
        expect(await client.query(node)).toEqual(1);
      }
    }

    // LHS = NS_n
    for (const rhsNdx in rhsAll) {
      if (rhsAll[rhsNdx] !== undefined) {
        const rhs = rhsAll[rhsNdx];
        node = opNoneCoalesce({lhs: NSNumberN, rhs: rhs as any});
        expect(node.type).toEqual(union(['number', rhs.type]));
        expect(await client.query(node)).toEqual(await client.query(rhs));
      }
    }

    // LHS = CLC
    for (const rhsNdx in rhsAll) {
      if (rhsAll[rhsNdx] !== undefined) {
        const rhs = rhsAll[rhsNdx];
        node = opNoneCoalesce({lhs: CLCNumber, rhs: rhs as any});
        expect(node.type).toEqual(list('number'));
        expect(await client.query(node)).toEqual([1, 2, 3, 4]);
      }
    }

    // LHS = CLN
    node = opNoneCoalesce({lhs: CLNNumber, rhs: CSString});
    expect(node.type).toEqual(list(union(['number', 'string'])));
    expect(await client.query(node)).toEqual([1, 'a', 3, 'a']);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: NSStringC});
    expect(node.type).toEqual(list(union(['number', 'none', 'string'])));
    expect(await client.query(node)).toEqual([1, 'a', 3, 'a']);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: NSStringN});
    expect(node.type).toEqual(list(union(['number', 'none', 'string'])));
    expect(await client.query(node)).toEqual([1, null, 3, null]);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: CLCString});
    expect(node.type).toEqual(list(union(['number', 'string'])));
    expect(await client.query(node)).toEqual([1, 'b', 3, 'd']);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: CLNString});
    expect(node.type).toEqual(list(union(['number', 'none', 'string'])));
    expect(await client.query(node)).toEqual([1, 'b', 3, null]);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: NLCStringC});
    expect(node.type).toEqual(
      union([list(maybe('number')), list(union(['number', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, 'b', 3, 'd']);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: NLCStringN});
    expect(node.type).toEqual(
      union([list(maybe('number')), list(union(['number', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, null, 3, null]);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: NLNStringC});
    expect(node.type).toEqual(
      union([list(maybe('number')), list(union(['number', 'none', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, 'b', 3, null]);
    node = opNoneCoalesce({lhs: CLNNumber, rhs: NLNStringN});
    expect(node.type).toEqual(
      union([list(maybe('number')), list(union(['number', 'none', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, null, 3, null]);

    // LHS = NLC_c
    for (const rhsNdx in rhsAll) {
      if (rhsAll[rhsNdx] !== undefined) {
        const rhs = rhsAll[rhsNdx];
        node = opNoneCoalesce({lhs: NLCNumberC, rhs: rhs as any});
        expect(node.type).toEqual(union([list('number'), rhs.type]));
        expect(await client.query(node)).toEqual([1, 2, 3, 4]);
      }
    }

    // LHS = NLC_n
    for (const rhsNdx in rhsAll) {
      if (rhsAll[rhsNdx] !== undefined) {
        const rhs = rhsAll[rhsNdx];
        node = opNoneCoalesce({lhs: NLCNumberN, rhs: rhs as any});
        expect(node.type).toEqual(union([list('number'), rhs.type]));
        expect(await client.query(node)).toEqual(await client.query(rhs));
      }
    }

    // LHS = NLN_c
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: CSString});
    expect(node.type).toEqual(
      union(['string', list(union(['number', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, 'a', 3, 'a']);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: NSStringC});
    expect(node.type).toEqual(
      union(['none', 'string', list(union(['number', 'none', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, 'a', 3, 'a']);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: NSStringN});
    expect(node.type).toEqual(
      union(['none', 'string', list(union(['number', 'none', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, null, 3, null]);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: CLCString});
    expect(node.type).toEqual(
      union([list('string'), list(union(['number', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, 'b', 3, 'd']);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: CLNString});
    expect(node.type).toEqual(
      union([
        list(union(['none', 'string'])),
        list(union(['number', 'none', 'string'])),
      ])
    );
    expect(await client.query(node)).toEqual([1, 'b', 3, null]);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: NLCStringC});
    expect(node.type).toEqual(
      union(['none', list('string'), list(union(['none', 'number', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, 'b', 3, 'd']);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: NLCStringN});
    expect(node.type).toEqual(
      union(['none', list('string'), list(union(['none', 'number', 'string']))])
    );
    expect(await client.query(node)).toEqual([1, null, 3, null]);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: NLNStringC});
    expect(node.type).toEqual(
      union([
        'none',
        list(union(['none', 'string'])),
        list(union(['number', 'none', 'string'])),
      ])
    );
    expect(await client.query(node)).toEqual([1, 'b', 3, null]);
    node = opNoneCoalesce({lhs: NLNNumberC, rhs: NLNStringN});
    expect(node.type).toEqual(
      union([
        'none',
        list(union(['none', 'string'])),
        list(union(['number', 'none', 'string'])),
      ])
    );
    expect(await client.query(node)).toEqual([1, null, 3, null]);

    // LHS = NLN_n
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: CSString});
    expect(node.type).toEqual(
      union(['string', list(union(['number', 'string']))])
    );
    expect(await client.query(node)).toEqual('a');
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: NSStringC});
    expect(node.type).toEqual(
      union(['none', 'string', list(union(['number', 'none', 'string']))])
    );
    expect(await client.query(node)).toEqual('a');
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: NSStringN});
    expect(node.type).toEqual(
      union(['none', 'string', list(union(['number', 'none', 'string']))])
    );
    expect(await client.query(node)).toEqual(null);
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: CLCString});
    expect(node.type).toEqual(
      union([list('string'), list(union(['number', 'string']))])
    );
    expect(await client.query(node)).toEqual(['a', 'b', 'c', 'd']);
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: CLNString});
    expect(node.type).toEqual(
      union([
        list(union(['none', 'string'])),
        list(union(['number', 'none', 'string'])),
      ])
    );
    expect(await client.query(node)).toEqual(['a', 'b', null, null]);
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: NLCStringC});
    expect(node.type).toEqual(
      union(['none', list('string'), list(union(['none', 'number', 'string']))])
    );
    expect(await client.query(node)).toEqual(['a', 'b', 'c', 'd']);
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: NLCStringN});
    expect(node.type).toEqual(
      union(['none', list('string'), list(union(['none', 'number', 'string']))])
    );
    expect(await client.query(node)).toEqual(null);
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: NLNStringC});
    expect(node.type).toEqual(
      union([
        'none',
        list(union(['none', 'string'])),
        list(union(['number', 'none', 'string'])),
      ])
    );
    expect(await client.query(node)).toEqual(['a', 'b', null, null]);
    node = opNoneCoalesce({lhs: NLNNumberN, rhs: NLNStringN});
    expect(node.type).toEqual(
      union([
        'none',
        list(union(['none', 'string'])),
        list(union(['number', 'none', 'string'])),
      ])
    );
    expect(await client.query(node)).toEqual(null);
  }, 10000);

  it('makeTagGetterOp should get all tags correctly', async () => {
    const client = await testClient();
    const testGetter = makeTagGetterOp({
      name: 'testGetter',
      tagName: 'testTag',
      tagType: 'number',
      hidden: true,
    });

    /*
    none
    tagged none (valid type, valid name, valid both)
    tagged string (valid type, valid name, valid both)
    nested tagged string (inner tag, outer tag)
    list nested tagged string (inner tag, outer tag)
    tagged list nested tagged string (inner tag, outer tag)
    */

    let node;
    node = testGetter({obj: constNodeUnsafe('none', null)});
    expect(node.type).toEqual('none');
    expect(await client.query(node)).toEqual(null);

    node = testGetter({
      obj: constNodeUnsafe(taggedValue(typedDict({a: 'number'}), 'none'), {
        _value: null,
        _tag: {a: 1},
      }),
    });
    expect(node.type).toEqual('none');
    expect(await client.query(node)).toEqual(null);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(typedDict({testTag: 'number'}), 'none'),
        {_value: null, _tag: {testTag: 1}}
      ),
    });
    expect(node.type).toEqual('number');
    expect(await client.query(node)).toEqual(1);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(typedDict({testTag: 'string'}), 'none'),
        {_value: null, _tag: {testTag: '1'}}
      ),
    });
    expect(node.type).toEqual('none');
    // This is not supported yet
    // expect(await client.query(node)).toEqual(null)

    node = testGetter({obj: constNodeUnsafe('string', 'a')});
    expect(node.type).toEqual('none');
    expect(await client.query(node)).toEqual(null);

    node = testGetter({
      obj: constNodeUnsafe(taggedValue(typedDict({a: 'number'}), 'string'), {
        _value: 'a',
        _tag: {a: 1},
      }),
    });
    expect(node.type).toEqual('none');
    expect(await client.query(node)).toEqual(null);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(typedDict({testTag: 'number'}), 'string'),
        {_value: 'a', _tag: {testTag: 1}}
      ),
    });
    expect(node.type).toEqual('number');
    expect(await client.query(node)).toEqual(1);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(typedDict({testTag: 'string'}), 'string'),
        {_value: 'a', _tag: {testTag: '1'}}
      ),
    });
    expect(node.type).toEqual('none');
    // This is not supported yet
    // expect(await client.query(node)).toEqual(null)

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(
          taggedValue(
            typedDict({testTag: 'number'}),
            typedDict({other: 'number'})
          ),
          'string'
        ),
        {_value: 'a', _tag: {_tag: {testTag: 1}, _value: {other: 2}}}
      ),
    });
    expect(node.type).toEqual('number');
    expect(await client.query(node)).toEqual(1);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(
          taggedValue(
            typedDict({other: 'number'}),
            typedDict({testTag: 'number'})
          ),
          'string'
        ),
        {_value: 'a', _tag: {_tag: {other: 2}, _value: {testTag: 1}}}
      ),
    });
    expect(node.type).toEqual({
      tag: {propertyTypes: {other: 'number'}, type: 'typedDict'},
      type: 'tagged',
      value: 'number',
    });
    expect(await client.query(node)).toEqual(1);

    node = testGetter({
      obj: constNodeUnsafe(
        list(
          taggedValue(
            taggedValue(
              typedDict({testTag: 'number'}),
              typedDict({other: 'number'})
            ),
            'string'
          )
        ),
        [
          {_value: 'a', _tag: {_tag: {testTag: 1}, _value: {other: 2}}},
          {_value: 'a', _tag: {_tag: {testTag: 2}, _value: {other: 2}}},
        ]
      ),
    });
    expect(node.type).toEqual(list('number'));
    expect(await client.query(node)).toEqual([1, 2]);

    node = testGetter({
      obj: constNodeUnsafe(
        list(
          taggedValue(
            taggedValue(
              typedDict({other: 'number'}),
              typedDict({testTag: 'number'})
            ),
            'string'
          )
        ),
        [
          {_value: 'a', _tag: {_tag: {other: 2}, _value: {testTag: 1}}},
          {_value: 'a', _tag: {_tag: {other: 2}, _value: {testTag: 2}}},
        ]
      ),
    });
    expect(node.type).toEqual(
      list({
        tag: {propertyTypes: {other: 'number'}, type: 'typedDict'},
        type: 'tagged',
        value: 'number',
      })
    );
    expect(await client.query(node)).toEqual([1, 2]);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(
          typedDict({outerOther: 'string'}),
          list(
            taggedValue(
              taggedValue(
                typedDict({testTag: 'number'}),
                typedDict({other: 'number'})
              ),
              'string'
            )
          )
        ),
        {
          _tag: {outerOther: 'b'},
          _value: [
            {_value: 'a', _tag: {_tag: {testTag: 1}, _value: {other: 2}}},
            {_value: 'a', _tag: {_tag: {testTag: 2}, _value: {other: 2}}},
          ],
        }
      ),
    });
    expect(node.type).toEqual(
      list(taggedValue(typedDict({outerOther: 'string'}), 'number'))
    );
    expect(await client.query(node)).toEqual([1, 2]);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(
          typedDict({outerOther: 'string'}),
          list(
            taggedValue(
              taggedValue(
                typedDict({other: 'number'}),
                typedDict({testTag: 'number'})
              ),
              'string'
            )
          )
        ),
        {
          _tag: {outerOther: 'b'},
          _value: [
            {_value: 'a', _tag: {_tag: {other: 2}, _value: {testTag: 1}}},
            {_value: 'a', _tag: {_tag: {other: 2}, _value: {testTag: 2}}},
          ],
        }
      ),
    });
    expect(node.type).toEqual(
      list(
        taggedValue(
          typedDict({outerOther: 'string'}),
          taggedValue(typedDict({other: 'number'}), 'number')
        )
      )
    );
    expect(await client.query(node)).toEqual([1, 2]);

    node = testGetter({
      obj: constNodeUnsafe(
        list(taggedValue(typedDict({other: 'number'}), 'string')),
        [
          {_value: 'a', _tag: {other: 2}},
          {_value: 'a', _tag: {other: 2}},
        ]
      ),
    });
    expect(node.type).toEqual('none');
    expect(await client.query(node)).toEqual(null);

    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(
          typedDict({testTag: 'number'}),
          list(taggedValue(typedDict({other: 'number'}), 'string'))
        ),
        {
          _tag: {testTag: 3},
          _value: [
            {_value: 'a', _tag: {other: 1}},
            {_value: 'a', _tag: {other: 2}},
          ],
        }
      ),
    });
    expect(node.type).toEqual('number');
    expect(await client.query(node)).toEqual(3);

    // This one is awkward! do you choose the outer or the inner? (i chose outer)
    node = testGetter({
      obj: constNodeUnsafe(
        taggedValue(
          typedDict({testTag: 'number'}),
          list(taggedValue(typedDict({testTag: 'number'}), 'string'))
        ),
        {
          _tag: {testTag: 3},
          _value: [
            {_value: 'a', _tag: {testTag: 1}},
            {_value: 'a', _tag: {testTag: 2}},
          ],
        }
      ),
    });
    expect(node.type).toEqual(
      list(taggedValue(typedDict({testTag: 'number'}), 'number'))
    );
    expect(await client.query(node)).toEqual([1, 2]);
  });
  it('1 = Tagged<1>', async () => {
    expect(
      await (
        await testClient()
      ).query(
        opNumberEqual({
          lhs: constNumber(1),
          rhs: constNodeUnsafe('any', concreteTaggedValue('unused', 1)),
        })
      )
    ).toEqual(true);
  });

  it('1 != Tagged<1>', async () => {
    expect(
      await (
        await testClient()
      ).query(
        opNumberNotEqual({
          lhs: constNumber(1),
          rhs: constNodeUnsafe('any', concreteTaggedValue('unused', 1)),
        })
      )
    ).toEqual(false);
  });

  it('Tagged<1> == Tagged<1>', async () => {
    expect(
      await (
        await testClient()
      ).query(
        opNumberEqual({
          lhs: constNodeUnsafe('any', concreteTaggedValue('unused', 1)),
          rhs: constNodeUnsafe('any', concreteTaggedValue('unused', 1)),
        })
      )
    ).toEqual(true);
  });

  it('Tagged<1> != Tagged<1>', async () => {
    expect(
      await (
        await testClient()
      ).query(
        opNumberNotEqual({
          lhs: constNodeUnsafe('any', concreteTaggedValue('unused', 1)),
          rhs: constNodeUnsafe('any', concreteTaggedValue('unused', 1)),
        })
      )
    ).toEqual(false);
  });
});

describe('opJoinAll return types', () => {
  it('simple case', () => {
    const joined = opJoinAll({
      arrs: constNodeUnsafe(list(list(typedDict({a: 'number'}))), null) as any,
      joinFn: constFunction({row: 'number'}, row => constNumber(5)) as any,
    } as any);
    expect(defaultLanguageBinding.printType(joined.type, false))
      .toEqual(`List<Tagged<
  tag: {
    joinKey:string
    joinObj:number
  }
  value: {
    a:List<number>
  }
>>`);
  });
  it('maybe inner list', () => {
    const joined = opJoinAll({
      arrs: constNodeUnsafe(
        list(maybe(list(typedDict({a: 'number'})))),
        null
      ) as any,
      joinFn: constFunction({row: 'number'}, row => constNumber(5)) as any,
    } as any);
    expect(defaultLanguageBinding.printType(joined.type, false))
      .toEqual(`List<Tagged<
  tag: {
    joinKey:string
    joinObj:number
  }
  value: {
    a:List<number>
  }
>>`);
  });
  it('maybe inner typedDict key', () => {
    const joined = opJoinAll({
      arrs: constNodeUnsafe(
        list(list(typedDict({a: maybe('number')}))),
        null
      ) as any,
      joinFn: constFunction({row: 'number'}, row => constNumber(5)) as any,
    } as any);
    expect(defaultLanguageBinding.printType(joined.type, false))
      .toEqual(`List<Tagged<
  tag: {
    joinKey:string
    joinObj:number
  }
  value: {
    a:List<Maybe<number>>
  }
>>`);
  });
  it('maybe tagged inner typedDict key', () => {
    const joined = opJoinAll({
      arrs: constNodeUnsafe(
        list(
          list(
            typedDict({
              a: maybe(taggedValue('string', 'number')),
            })
          )
        ),
        null
      ) as any,
      joinFn: constFunction({row: 'number'}, row => constNumber(5)) as any,
    } as any);
    expect(defaultLanguageBinding.printType(joined.type, false))
      .toEqual(`List<Tagged<
  tag: {
    joinKey:string
    joinObj:number
  }
  value: {
    a:List<Maybe<Tagged<
        tag: string
        value: number
      >>>
  }
>>`);
  });
});
