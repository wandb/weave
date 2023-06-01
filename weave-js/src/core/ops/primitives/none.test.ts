import {maybe, taggedValue} from '../../model';
import {
  constBoolean,
  constNode,
  constNone,
  constNumber,
  constString,
} from '../../model';
import {testNode} from '../../testUtil';
import {opIsNone} from './none';

describe('none ops', () => {
  describe('opIsNone', () => {
    it('handles single none', async () => {
      await testNode(
        opIsNone({
          val: constNone(),
        }),
        {
          type: 'boolean',
          value: true,
        }
      );
    });

    it('handles single value', async () => {
      await testNode(
        opIsNone({
          val: constNumber(1),
        }),
        {
          type: 'boolean',
          value: false,
        }
      );
    });

    it('handles single tagged value', async () => {
      await testNode(
        opIsNone({
          val: constNode(
            taggedValue('string' as const, maybe('number' as const)),
            {
              _tag: 'hello',
              _value: 1,
            }
          ),
        }),
        {
          type: 'boolean',
          value: false,
        }
      );
    });

    it('handles single tagged value - null', async () => {
      await testNode(
        opIsNone({
          val: constNode(
            taggedValue('string' as const, maybe('number' as const)),
            {
              _tag: 'hello',
              _value: null,
            }
          ),
        }),
        {
          type: 'boolean',
          value: true,
        }
      );
    });

    it('handles single value - 0', async () => {
      await testNode(
        opIsNone({
          val: constNumber(0),
        }),
        {
          type: 'boolean',
          value: false,
        }
      );
    });

    it('handles single value empty string', async () => {
      await testNode(
        opIsNone({
          val: constString(''),
        }),
        {
          type: 'boolean',
          value: false,
        }
      );
    });

    it('handles single value false', async () => {
      await testNode(
        opIsNone({
          val: constBoolean(false),
        }),
        {
          type: 'boolean',
          value: false,
        }
      );
    });
  });
});
