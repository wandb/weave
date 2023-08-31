/* tslint:disable */

import {Options, pineapple, unpineapple} from './pineapple';

describe('pineapple/unpineapple', () => {
  function testCase(raw: any, transformed: any, opts?: Partial<Options>) {
    let rawObj = JSON.stringify(raw);
    let truncated = '... (TRUNCATED)';
    if (rawObj != null && rawObj.length > 100) {
      rawObj = rawObj.substring(0, 100 - truncated.length) + truncated;
    } else if (typeof rawObj === 'undefined') {
      rawObj = '(undefined)';
    }
    const label = `${
      opts ? JSON.stringify(opts) : '(default options)'
    } ${rawObj}`;
    it(label, () => {
      const pineappled = pineapple(raw, opts);
      expect(pineappled).toEqual(transformed);

      const unpineappled = unpineapple(transformed, opts);
      expect(unpineappled).toEqual(raw);
    });
  }

  function throwCase(
    raw: any,
    transformed: any,
    expectedError: string,
    opts?: Partial<Options>
  ) {
    it(`${opts ? JSON.stringify(opts) : '(default options)'} ${JSON.stringify(
      raw
    )} THROWS ${JSON.stringify(expectedError)}`, () => {
      expect(() => {
        const pineappled = pineapple(raw, opts);
        expect(pineappled).toEqual(transformed);

        const unpineappled = unpineapple(transformed, opts);
        expect(unpineappled).toEqual(raw);
      }).toThrowError(expectedError);
    });
  }

  describe('primitives', () => {
    testCase(42, {'🍍': 42});
    testCase(0, {'🍍': 0});
    testCase('string', {'🍍': 'string'});
    testCase('', {'🍍': ''});
    testCase(true, {'🍍': true});
    testCase(false, {'🍍': false});
    testCase(null, {'🍍': null});
    testCase(undefined, {'🍍': '🍍🍍_undef_'});
  });

  describe('objects', () => {
    testCase(
      {},
      {
        '🍍': {'🍍': 0},
        refs: [{}],
      }
    );
    testCase(
      {
        foo: 'hello',
      },
      {
        '🍍': {'🍍': 0},
        refs: [{foo: 'hello'}],
      }
    );
    testCase(
      {
        foo: {
          bar: 'hello',
        },
      },
      {refs: [{foo: {'🍍': 1}}, {bar: 'hello'}], '🍍': {'🍍': 0}}
    );
    testCase(
      {
        foo: {
          bar: {
            baz: {
              a: 42,
              b: 0,
              c: 'string',
              d: '',
              e: true,
              f: false,
              g: null,
              h: {},
            },
          },
        },
      },
      {
        refs: [
          {foo: {'🍍': 1}},
          {bar: {'🍍': 2}},
          {baz: {'🍍': 3}},
          {
            a: 42,
            b: 0,
            c: 'string',
            d: '',
            e: true,
            f: false,
            g: null,
            h: {'🍍': 4},
          },
          {},
        ],
        '🍍': {'🍍': 0},
      }
    );
  });

  describe('arrays', () => {
    testCase([42, 0, 'string', '', true, false, null], {
      refs: [[42, 0, 'string', '', true, false, null]],
      '🍍': {'🍍': 0},
    });
    testCase([[[[42, 0, 'string', '', true, false, null]]]], {
      refs: [
        [{'🍍': 1}],
        [{'🍍': 2}],
        [{'🍍': 3}],
        [42, 0, 'string', '', true, false, null],
      ],
      '🍍': {'🍍': 0},
    });
  });

  describe('mixed', () => {
    testCase(
      [
        {
          a: [
            {
              b: [{c: null}],
            },
          ],
        },
      ],
      {
        refs: [
          [{'🍍': 1}],
          {a: {'🍍': 2}},
          [{'🍍': 3}],
          {b: {'🍍': 4}},
          [{'🍍': 5}],
          {c: null},
        ],
        '🍍': {'🍍': 0},
      }
    );
  });

  describe('obj equality', () => {
    testCase(
      {
        a: {foo: 123},
        b: {foo: 123},
        c: {foo: 123},
      },
      {
        refs: [
          {a: {'🍍': 1}, b: {'🍍': 2}, c: {'🍍': 3}},
          {foo: 123},
          {foo: 123},
          {foo: 123},
        ],
        '🍍': {'🍍': 0},
      }
    );
  });

  describe('ref equality', () => {
    const obj = {foo: 123};
    testCase(
      {
        a: obj,
        b: obj,
        c: obj,
      },
      {
        refs: [{a: {'🍍': 1}, b: {'🍍': 1}, c: {'🍍': 1}}, {foo: 123}],
        '🍍': {'🍍': 0},
      }
    );
    testCase([obj, obj, obj], {
      refs: [[{'🍍': 1}, {'🍍': 1}, {'🍍': 1}], {foo: 123}],
      '🍍': {'🍍': 0},
    });
    testCase(
      {a: {b: obj, c: obj}, d: obj},
      {
        refs: [
          {a: {'🍍': 1}, d: {'🍍': 2}},
          {b: {'🍍': 2}, c: {'🍍': 2}},
          {foo: 123},
        ],
        '🍍': {'🍍': 0},
      }
    );
  });

  describe('key collisions', () => {
    testCase({'🍍': 'foobar'}, {'🍍': {'🍍': 0}, refs: [{'🍍': 'foobar'}]});
    testCase({'🍍': true}, {'🍍': {'🍍': 0}, refs: [{'🍍': true}]});
    testCase({'🍍': null}, {'🍍': {'🍍': 0}, refs: [{'🍍': null}]});
    testCase({'🍍': 42}, {refs: [{'🍍': {'🍍🍍': 42}}], '🍍': {'🍍': 0}});
    testCase(
      {a: {'🍍': 42}},
      {refs: [{a: {'🍍': 1}}, {'🍍': {'🍍🍍': 42}}], '🍍': {'🍍': 0}}
    );
    throwCase(
      {'🍍🍍': 42},
      null,
      'Cannot encode object containing doubled key ("🍍🍍")'
    );
  });

  describe('alt key', () => {
    testCase(
      {'🍍🍍': 42},
      {refs: [{'🍍🍍': {'🍍🍍🍍🍍': 42}}], '🍍🍍': {'🍍🍍': 0}},
      {key: '🍍🍍'}
    );
    testCase(
      {'🍍🍍': 42},
      {refs: [{'🍍🍍': {'🍍🍍🍍🍍': 42}}], '🍍🍍': {'🍍🍍': 0}},
      {key: '🍍🍍'}
    );
    testCase(
      {foo: 'bar'},
      {'🦄': {'🦄': 0}, refs: [{foo: 'bar'}]},
      {
        key: '🦄',
      }
    );
    testCase(
      {foo: 'bar'},
      {key: {key: 0}, refs: [{foo: 'bar'}]},
      {
        key: 'key',
      }
    );
    throwCase(
      {'🦄🦄': true},
      null,
      'Cannot encode object containing doubled key ("🦄🦄")',
      {key: '🦄'}
    );
    throwCase(
      {'🦄🦄🦄🦄': 'foobar'},
      null,
      'Cannot encode object containing doubled key ("🦄🦄🦄🦄")',
      {key: '🦄🦄'}
    );
  });

  describe('programming errors', () => {
    throwCase({foo: 'bar'}, null, 'key must be non-empty, non-numeric string', {
      key: null,
    } as any);
    throwCase({foo: 'bar'}, null, 'key must be non-empty, non-numeric string', {
      key: '',
    });
    throwCase({foo: 'bar'}, null, 'key must be non-empty, non-numeric string', {
      key: '42',
    });
    throwCase({foo: 'bar'}, null, 'key must be non-empty, non-numeric string', {
      key: true as any,
    });
  });

  describe('stress', () => {
    const a = {
      a: 42,
      b: 0,
      c: 'string',
      d: '',
      e: true,
      f: false,
      g: null,
      h: {},
      '🍍': 1,
    };
    const b = {
      a: a,
      b: a,
      c: a,
      d: a,
      e: a,
      f: a,
      g: a,
      h: a,
    };
    const c = [b, b, b, b, b, b, b, b];
    const d = {
      a: c,
      b: c,
      c: c,
      d: c,
      e: c,
      f: c,
      g: c,
      h: c,
    };
    testCase(d, {
      refs: [
        {
          a: {'🍍': 1},
          b: {'🍍': 1},
          c: {'🍍': 1},
          d: {'🍍': 1},
          e: {'🍍': 1},
          f: {'🍍': 1},
          g: {'🍍': 1},
          h: {'🍍': 1},
        },
        [
          {'🍍': 2},
          {'🍍': 2},
          {'🍍': 2},
          {'🍍': 2},
          {'🍍': 2},
          {'🍍': 2},
          {'🍍': 2},
          {'🍍': 2},
        ],
        {
          a: {'🍍': 3},
          b: {'🍍': 3},
          c: {'🍍': 3},
          d: {'🍍': 3},
          e: {'🍍': 3},
          f: {'🍍': 3},
          g: {'🍍': 3},
          h: {'🍍': 3},
        },
        {
          a: 42,
          b: 0,
          c: 'string',
          d: '',
          e: true,
          f: false,
          g: null,
          h: {'🍍': 4},
          '🍍': {'🍍🍍': 1},
        },
        {},
      ],
      '🍍': {'🍍': 0},
    });
  });
});
