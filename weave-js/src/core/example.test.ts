import {constString} from './model';
import {opStringAdd} from './ops';
import {testNode} from './testUtil';

describe('<type> Ops', () => {
  it('test <opname>', async () => {
    await testNode(
      opStringAdd({
        lhs: constString('hello'),
        rhs: constString(' world'),
      }),
      {
        type: 'string',
        resolvedType: 'string',
        value: 'hello world',
      }
    );
  });
});
