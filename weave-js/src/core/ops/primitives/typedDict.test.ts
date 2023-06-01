import {
  constBoolean,
  constNumber,
  constString,
  list,
  maybe,
  union,
} from '../../model';
import {testNode} from '../../testUtil';
import {opArray, opDict} from './literals';
import {opStringSlice} from './string';
import {opPick} from './typedDict';

describe('TypedDict Ops', () => {
  it('opPick - simple', async () => {
    await testNode(
      opPick({
        obj: opDict({a: constNumber(42)} as any),
        key: constString('a'),
      }),

      {
        type: 'number' as const,
        value: 42,
      }
    );
  });

  it('opPick - mixed', async () => {
    await testNode(
      opPick({
        obj: opArray({
          0: opDict({a: constNumber(42)} as any),
          1: opDict({
            a: constString('hello'),
            b: constBoolean(false),
          } as any),
        } as any),
        key: constString('a'),
      }),
      {
        type: list(union(['number', 'string']), 2, 2),
        value: [42, 'hello'],
      }
    );
  });

  it('opPick - mixed with non-constant key', async () => {
    await testNode(
      opPick({
        obj: opArray({
          0: opDict({a: constNumber(42)} as any),
          1: opDict({
            a: constString('hello'),
            b: constBoolean(false),
          } as any),
        } as any),
        key: opStringSlice({
          str: constString('abc'),
          begin: constNumber(0),
          end: constNumber(1),
        }),
      }),
      {
        type: list(maybe(union(['number', 'string', 'boolean'])), 2, 2),
        value: [42, 'hello'],
      }
    );
  });
});
