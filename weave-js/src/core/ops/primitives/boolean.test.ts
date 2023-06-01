import {constBoolean, constNone} from '../../model';
import {testNode} from '../../testUtil';
import {opNot} from './boolean';

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
