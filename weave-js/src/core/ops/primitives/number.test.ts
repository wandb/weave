import {
  constNodeUnsafe,
  constNumber,
  constNumberList,
  list,
  maybe,
  taggedValue,
} from '../../model';
import {testClient} from '../../testUtil';
import {opNumberFloor, opNumberToTimestamp} from './number';

describe('number ops', () => {
  describe('floor', () => {
    it('handles single number', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNumber(3.14),
      });
      expect(await client.query(expr)).toEqual(3);
    });

    it('handles null', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNodeUnsafe(maybe('number'), null),
      });
      expect(await client.query(expr)).toEqual(null);
    });

    it('handles tagged number', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNodeUnsafe(taggedValue('string', 'number'), {
          _tag: 'x',
          _value: 3.14,
        }),
      });
      expect(await client.query(expr)).toEqual(3);
    });

    it('handles tagged null', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNodeUnsafe(taggedValue('string', maybe('number')), {
          _tag: 'x',
          _value: null,
        }),
      });
      expect(await client.query(expr)).toEqual(null);
    });

    it('handles list of numbers', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNumberList([2.72, 3.14]),
      });
      expect(await client.query(expr)).toEqual([2, 3]);
    });

    it('handles list of numbers containing null', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNodeUnsafe(list(maybe('number')), [2.72, null, 3.14]),
      });
      expect(await client.query(expr)).toEqual([2, null, 3]);
    });

    it('handles tagged list of numbers', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNodeUnsafe(list(taggedValue('string', 'number')), [
          {_tag: 'x', _value: 1.23},
          {_tag: 'y', _value: 2.34},
        ]),
      });
      expect(await client.query(expr)).toEqual([1, 2]);
    });

    it('handles tagged list of numbers containing null', async () => {
      const client = await testClient();
      const expr = opNumberFloor({
        in: constNodeUnsafe(list(taggedValue('string', maybe('number'))), [
          {_tag: 'x', _value: 1.23},
          {_tag: 'y', _value: null},
          {_tag: 'z', _value: 2.34},
        ]),
      });
      expect(await client.query(expr)).toEqual([1, null, 2]);
    });
  });

  describe('timestamp', () => {
    it('handles a unix timestamp in miliseconds', async () => {
      const client = await testClient();
      const expr = opNumberToTimestamp({val: constNumber(1729000000000)});
      expect(await client.query(expr)).toEqual(1729000000000);
    });

    it('handles a unix timestamp in microseconds by converting to ms', async () => {
      const client = await testClient();
      const expr = opNumberToTimestamp({
        val: constNumber(1729000000000 * 1000 * 1000),
      });
      expect(await client.query(expr)).toEqual(1729000000000);
    });

    it('handles a unix timestamp in nanoseconds by converting to ms', async () => {
      const client = await testClient();
      const expr = opNumberToTimestamp({
        val: constNumber(1729000000000 * 1000 * 1000 * 1000),
      });
      expect(await client.query(expr)).toEqual(1729000000000);
    });

    it('handles negative numbers', async () => {
      const client = await testClient();
      const expr = opNumberToTimestamp({
        val: constNumber(-1 * 1729000000000 * 1000 * 1000 * 1000),
      });
      expect(await client.query(expr)).toEqual(-1729000000000);
    });

    it('handles a unix timestamp in seconds by doing nothing', async () => {
      const client = await testClient();
      const expr = opNumberToTimestamp({val: constNumber(1729000000)});
      expect(await client.query(expr)).toEqual(1729000000);
    });
  });
});
