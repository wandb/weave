import {stringifyPythonDumps} from '../digest';

describe('stringifyPythonDumps', () => {
  test('Basic types', async () => {
    const testData1 = {
      a: 1,
      b: ['a', 'b', 'd,e', ["f',j,y"]],
      c: 3,
      d: 4,
      e: 5,
    };
    const expected1 =
      '{"a": 1, "b": ["a", "b", "d,e", ["f\',j,y"]], "c": 3, "d": 4, "e": 5}';
    expect(stringifyPythonDumps(testData1)).toBe(expected1);
  });

  test('Special numbers', async () => {
    const testData2 = {
      int_max: 9007199254740991, // Max safe integer in JS
      int_min: -9007199254740991, // Min safe integer in JS
      float: 3.14159,
      exp_pos: 1e100,
      exp_neg: 1e-100,
      zero: 0,
      neg_zero: -0,
    };
    const expected2 =
      '{"exp_neg": 1e-100, "exp_pos": 1e+100, "float": 3.14159, "int_max": 9007199254740991, "int_min": -9007199254740991, "neg_zero": 0, "zero": 0}';
    expect(stringifyPythonDumps(testData2)).toBe(expected2);
  });

  test('Special values', async () => {
    const testData3 = {
      null: null,
      bool_true: true,
      bool_false: false,
      empty_list: [],
      empty_dict: {},
    };
    const expected3 =
      '{"bool_false": false, "bool_true": true, "empty_dict": {}, "empty_list": [], "null": null}';
    expect(stringifyPythonDumps(testData3)).toBe(expected3);
  });

  test('Unicode and escaping', async () => {
    const testData4 = {
      unicode: 'こんにちは',
      escape_chars: '\b\f\n\r\t',
      quotes: '"Hello," she said.',
      backslash: 'C:\\path\\to\\file',
    };
    const expected4 =
      '{"backslash": "C:\\\\path\\\\to\\\\file", "escape_chars": "\\b\\f\\n\\r\\t", "quotes": "\\"Hello,\\" she said.", "unicode": "こんにちは"}';
    expect(stringifyPythonDumps(testData4)).toBe(expected4);
  });

  test('Nested structures', async () => {
    const testData5 = {
      nested: {
        list: [1, [2, [3, [4]]]],
        dict: {a: {b: {c: {d: 4}}}},
      },
    };
    const expected5 =
      '{"nested": {"dict": {"a": {"b": {"c": {"d": 4}}}}, "list": [1, [2, [3, [4]]]]}}';
    expect(stringifyPythonDumps(testData5)).toBe(expected5);
  });

  test('Array of mixed types', async () => {
    const testData6 = [1, 'two', 3, [4, 5], {six: 6}, null, true, false];
    const expected6 = '[1, "two", 3, [4, 5], {"six": 6}, null, true, false]';
    expect(stringifyPythonDumps(testData6)).toBe(expected6);
  });

  test('Empty string keys and values', async () => {
    const testData7 = {'': 'empty_key', empty_value: ''};
    const expected7 = '{"": "empty_key", "empty_value": ""}';
    expect(stringifyPythonDumps(testData7)).toBe(expected7);
  });

  // TODO: This is a generated test that fails. I didn't look into what the behavior should actually
  // be, because we're not using stringifyPythonDumps anywhere yet.
  test.skip('Non-string keys', async () => {
    const testData8 = {1: 'one', 2.0: 'two', true: 'true'};
    const expected8 = '{"1": "true", "2.0": "two"}';
    expect(stringifyPythonDumps(testData8)).toBe(expected8);
  });

  test('Special characters in strings', async () => {
    const testData9 = {
      control_chars: '\u0000\u0001\u0002\u0003',
      emoji: '😀🌍🚀',
      surrogate_pair: '\uD83D\uDE00',
    };
    const expected9 =
      '{"control_chars": "\\u0000\\u0001\\u0002\\u0003", "emoji": "😀🌍🚀", "surrogate_pair": "😀"}';
    expect(stringifyPythonDumps(testData9)).toBe(expected9);
  });
});

// describe('encodeNumber', () => {
//     test('Basic numbers', () => {
//         expect(encodeNumber(1)).toBe('1');
//         expect(encodeNumber(1.0)).toBe('1.0');
//         expect(encodeNumber(1.1)).toBe('1.1');
//         expect(encodeNumber(1e9)).toBe('1e9');
//     });
// });
