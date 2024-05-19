import {
  constBoolean,
  constNone,
  constNumber,
  constString,
  maybe,
  union,
} from '../../model';
import {testNode} from '../../testUtil';
import {opNot, weaveIf} from './boolean';

describe('Boolean Ops', () => {
  it('test opNot - simple', async () => {
    await testNode(opNot({bool: constBoolean(true)}), {
      type: 'boolean',
      value: false,
    });

    await testNode(opNot({bool: constBoolean(false)}), {
      type: 'boolean',
      value: true,
    });

    await testNode(opNot({bool: constNone()}), {
      type: 'none',
      value: null,
    });
  });
});

describe('Conditionals', () => {
  it('test if true', async () => {
    await testNode(
      weaveIf(constBoolean(true), constNumber(1), constNumber(2)),
      {
        type: maybe('number'),
        value: 1,
      }
    );
  });
  it('test if false', async () => {
    await testNode(
      weaveIf(constBoolean(false), constNumber(1), constNumber(2)),
      {
        type: maybe('number'),
        value: 2,
      }
    );
  });
  it('test if union output type', async () => {
    await testNode(
      weaveIf(constBoolean(false), constString('a'), constNumber(2)),
      {
        type: maybe(union(['string', 'number'])),
        value: 2,
      }
    );
  });
});
