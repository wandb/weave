import {
  constBoolean,
  constNone,
  constNumber,
  constString,
  union,
} from '../../model';
import {testNode} from '../../testUtil';
import {opIf} from './controlFlow';

describe('Control Flow Ops', () => {
  it('test opIf - simple true', async () => {
    await testNode(
      opIf({
        condition: constBoolean(true),
        then: constNumber(1) as any,
        else: constString('2') as any,
      }),
      {
        type: union(['number', 'string']),
        resolvedType: 'number',
        value: 1,
      }
    );
  });

  it('test opIf - simple false', async () => {
    await testNode(
      opIf({
        condition: constBoolean(false),
        then: constNumber(1) as any,
        else: constString('2') as any,
      }),
      {
        type: union(['number', 'string']),
        resolvedType: 'string',
        value: '2',
      }
    );
  });

  // Should this be null instead of the else?
  it('test opIf - null', async () => {
    await testNode(
      opIf({
        condition: constNone(),
        then: constNumber(1) as any,
        else: constString('2') as any,
      }),
      {
        type: union(['number', 'string']),
        resolvedType: 'string',
        value: '2',
      }
    );
  });
});
