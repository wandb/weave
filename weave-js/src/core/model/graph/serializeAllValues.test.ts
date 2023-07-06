import {
  opDateToNumber,
  opMap,
  opNumberEqual,
  opPick,
  opProjectCreatedAt,
  opProjectName,
  opProjectRuns,
  opRootProject,
  opRunName,
  opRunSummary,
} from '../../ops';
import {
  constDate,
  constFunction,
  constString,
  varNode,
  voidNode,
} from './construction';
import {serializeAllValues, deserializeAllValues} from './serializeAllValues';

describe('serializeAllValues', () => {
  it.each([
    // These graphs were taken from `serialize.test.ts`

    // simple query with var
    [
      opRunName({
        run: varNode('run', 'x'),
      }),
    ],

    // simple query with void
    [
      opRunName({
        run: voidNode() as any,
      }),
    ],

    // basic consts
    [
      opProjectName({
        project: opRootProject({
          entityName: constString('entity'),
          projectName: constString('project'),
        }),
      }),
    ],

    // complex single result
    [
      opMap({
        arr: opProjectRuns({
          project: opRootProject({
            entityName: constString('entity'),
            projectName: constString('project'),
          }),
        }) as any,
        mapFn: constFunction({row: 'run'}, ({row}) =>
          opRunName({
            run: row,
          })
        ) as any,
      }),
    ],

    // date
    [
      opNumberEqual({
        lhs: opDateToNumber({
          date: opProjectCreatedAt({
            project: opRootProject({
              entityName: constString('entity'),
              projectName: constString('project'),
            }),
          }),
        }),
        rhs: constDate(new Date(0)),
      }),
    ],

    // TODO: determine what this graph is supposed to test
    [
      opPick({
        obj: opRunSummary({run: varNode('run', 'row')}),
        key: constString('x'),
      }),
    ],
  ])('correctly deserializes back serialized object', graph => {
    const serialized = serializeAllValues([graph]);
    const deserialized = deserializeAllValues(serialized);
    expect(deserialized).toStrictEqual([graph]);

    // Check that we retain duplicate nodes in input array.
    // Otherwise, we lose context of what was originally requested by caller.
    const serializedWithDuplicates = serializeAllValues([graph, graph, graph]);
    const deserializedWithDuplicates = deserializeAllValues(
      serializedWithDuplicates
    );
    expect(deserializedWithDuplicates).toStrictEqual([graph, graph, graph]);
  });

  it(`correctly serializes dates`, () => {
    const graph = opNumberEqual({
      lhs: opDateToNumber({
        date: opProjectCreatedAt({
          project: opRootProject({
            entityName: constString('entity'),
            projectName: constString('project'),
          }),
        }),
      }),
      // `new Date(0)` should be serialized as `{type: 'date', val: '1970-01-01T00:00:00.000Z'}`
      rhs: constDate(new Date(0)),
    });

    const serialized = serializeAllValues([graph]);
    expect(serialized.nodes[16]).toBe(`date`);
    expect(serialized.nodes[34]).toBe(`1970-01-01T00:00:00.000Z`);
    expect(serialized.nodes[35]).toStrictEqual({type: 16, val: 34});
  });
});
