import {defaultLanguageBinding} from './language';
import {
  constFunction,
  constNodeUnsafe,
  constNumber,
  constNumberList,
  constString,
  list,
  typedDict,
} from './model';
import {
  opArray,
  opDict,
  opGroupby,
  opGroupGroupKey,
  opIndex,
  opLimit,
  opPick,
  opSort,
} from './ops';
import {simplify} from './simplify';
import {testClient} from './testUtil';

const arr1Value = [
  {a: 1, b: 2, c: 3},
  {a: 2, b: 3, c: 3},
  {a: 5, b: 3, c: 3},
];

const arr1ObjType = typedDict({
  a: 'number' as const,
  b: 'number' as const,
  c: 'number' as const,
});

const arr1 = constNodeUnsafe(list(arr1ObjType), arr1Value);

describe('simplify', () => {
  it('no simplification for just index', async () => {
    const client = await testClient();
    const node = opIndex({
      arr: constNumberList([1]) as any,
      index: constNumber(2),
    });
    expect(
      defaultLanguageBinding.printGraph(await simplify(client, node))
    ).toEqual(`[1][2]`);
  });
  it('simplifies opLimit when limit is smaller', async () => {
    const client = await testClient();
    const node = opIndex({
      arr: opLimit({
        arr: constNumberList([1]) as any,
        limit: constNumber(10),
      }) as any,
      index: constNumber(2),
    });
    const simple = await simplify(client, node);
    expect(defaultLanguageBinding.printGraph(simple)).toEqual(`[1][2]`);
    expect(await client.query(simple)).toEqual(await client.query(node));
  });
  it('doesnt simplify opLimit when limit is >=', async () => {
    const client = await testClient();
    const node = opIndex({
      arr: opLimit({
        arr: constNumberList([1]) as any,
        limit: constNumber(2),
      }) as any,
      index: constNumber(2),
    });
    expect(
      defaultLanguageBinding.printGraph(await simplify(client, node))
    ).toEqual(
      `[1]
  .limit(2)[2]`
    );
  });
  it('simplifies multiple', async () => {
    const client = await testClient();
    const node = opIndex({
      arr: opLimit({
        arr: opIndex({
          arr: opLimit({
            arr: constNodeUnsafe(list(list('number')), [[1]]) as any,
            limit: constNumber(10),
          }) as any,
          index: constNumber(2),
        }) as any,
        limit: constNumber(10),
      }) as any,
      index: constNumber(2),
    });
    const simple = await simplify(client, node);
    expect(defaultLanguageBinding.printGraph(simple)).toEqual(`[[1]][2][2]`);
  });
  it('groupBy()[1] becomes filter()', async () => {
    const client = await testClient();
    const grouped = opGroupby({
      arr: arr1 as any,
      groupByFn: constFunction({row: arr1ObjType}, ({row}) =>
        opPick({
          obj: row,
          key: constString('b'),
        })
      ) as any,
    });
    const group0 = opIndex({arr: grouped as any, index: constNumber(0)});
    const simple = await simplify(client, group0);
    expect(defaultLanguageBinding.printGraph(simple)).toEqual(
      `[{"a":1,"b":2,"c":3},{"a":2,"b":3,"c":3},{"a":5,"b":3,"c":3}]
  .filter((row) => row["b"] == 2)`
    );
    const simpleRes = await client.query(simple);
    const group0Res = await client.query(group0);
    expect(simpleRes).toEqual(group0Res);
  });
  it('groupBy().sort()[1] becomes filter()', async () => {
    const client = await testClient();
    const grouped = opSort({
      arr: opGroupby({
        arr: arr1 as any,
        groupByFn: constFunction({row: arr1ObjType}, ({row}) =>
          opPick({
            obj: row,
            key: constString('b'),
          })
        ),
      }) as any,
      compFn: constFunction({row: arr1ObjType}, ({row}) =>
        opPick({
          obj: row,
          key: constString('a'),
        })
      ),
      columnDirs: opArray({0: constString('desc')} as any) as any,
    });
    const group0 = opIndex({arr: grouped as any, index: constNumber(0)});
    const simple = await simplify(client, group0);
    expect(defaultLanguageBinding.printGraph(simple)).toEqual(
      `[{"a":1,"b":2,"c":3},{"a":2,"b":3,"c":3},{"a":5,"b":3,"c":3}]
  .filter((row) => row["b"] == 3)`
    );
  });
  it('groupBy()[1] with (groupBy with dict output)', async () => {
    const client = await testClient();
    const grouped = opGroupby({
      arr: arr1 as any,
      groupByFn: constFunction({row: arr1ObjType}, ({row}) =>
        opDict({
          b: opPick({
            obj: row,
            key: constString('b'),
          }),
          a: opPick({
            obj: row,
            key: constString('a'),
          }),
        } as any)
      ) as any,
    });
    const group0 = opIndex({arr: grouped as any, index: constNumber(0)});
    const simple = await simplify(client, group0);
    expect(defaultLanguageBinding.printGraph(simple)).toEqual(
      `[{"a":1,"b":2,"c":3},{"a":2,"b":3,"c":3},{"a":5,"b":3,"c":3}]
  .filter((row) => row["b"] == 2 and row["a"] == 1)`
    );
  });
  it('no simplification when getTag present', async () => {
    const client = await testClient();
    const grouped = opGroupby({
      arr: arr1 as any,
      groupByFn: constFunction({row: arr1ObjType}, ({row}) =>
        opPick({
          obj: row,
          key: constString('b'),
        })
      ) as any,
    });
    const group0 = opIndex({arr: grouped as any, index: constNumber(0)});
    const tag = opGroupGroupKey({obj: group0});
    const simple = await simplify(client, tag);

    expect(simple).toEqual(tag);
  });
});
