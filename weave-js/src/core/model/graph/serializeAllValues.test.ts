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
    [
      opRunName({
        run: varNode('run', 'x'),
      }),
      opRunName({
        run: voidNode() as any,
      }),
      opProjectName({
        project: opRootProject({
          entityName: constString('entity'),
          projectName: constString('project'),
        }),
      }),
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
      opPick({
        obj: opRunSummary({run: varNode('run', 'row')}),
        key: constString('x'),
      }),
    ],
  ])('correctly deserializes back serialized object', graph => {
    const serialized = serializeAllValues([graph]);
    const deserialized = deserializeAllValues(serialized);
    expect(deserialized).toStrictEqual([graph]);
  });
});
