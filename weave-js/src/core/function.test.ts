import {constFunction, constNumber, list, listObjectType, union} from './model';
import {
  opArray,
  opCount,
  opFilter,
  opNumberEqual,
  opNumberLessEqual,
} from './ops';
import {testNode} from './testUtil';

describe('Weave Functions', () => {
  it('test nested filter function', async () => {
    const arrN = opArray({
      0: opArray({0: constNumber(0)} as any),
      1: opArray({0: constNumber(0), 1: constNumber(1)} as any),
      2: opArray({
        0: constNumber(0),
        1: constNumber(1),
        2: constNumber(2),
      } as any),
    } as any);
    const arrNType = listObjectType(arrN.type);
    const filtered = opFilter({
      arr: arrN,
      filterFn: constFunction({row: arrNType}, ({row}) => {
        const eleType = listObjectType(row.type);
        const innerFiltered = opFilter({
          arr: row,
          filterFn: constFunction({row: eleType}, ({row: row2}) => {
            return opNumberLessEqual({
              lhs: row2,
              rhs: constNumber(1),
            });
          }),
        });
        return opNumberEqual({
          lhs: opCount({arr: innerFiltered}),
          rhs: constNumber(2),
        });
      }),
    });
    await testNode(filtered, {
      type: list(
        union([
          list('number', 1, 1),
          list('number', 2, 2),
          list('number', 3, 3),
        ]),
        3,
        3
      ),
      value: [
        [0, 1],
        [0, 1, 2],
      ],
    });
  });
});
