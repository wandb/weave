import {flattenObject, inferSchema, inferType} from './schemaUtils';

describe('inferType', () => {
  test('identifies null type', () => {
    expect(inferType(null)).toBe('null');
  });

  test('identifies array type', () => {
    expect(inferType([])).toBe('array');
    expect(inferType([1, 2, 3])).toBe('array');
  });

  test('identifies date type', () => {
    expect(inferType(new Date())).toBe('date');
  });

  test('identifies object type', () => {
    expect(inferType({})).toBe('object');
    expect(inferType({key: 'value'})).toBe('object');
  });

  test('identifies primitive types', () => {
    expect(inferType('string')).toBe('string');
    expect(inferType(42)).toBe('number');
    expect(inferType(true)).toBe('boolean');
    expect(inferType(undefined)).toBe('undefined');
  });
});

describe('flattenObject', () => {
  test('flattens simple object', () => {
    const result = flattenObject({a: 1, b: 'test'});
    expect(result).toEqual([
      {name: 'a', type: 'number'},
      {name: 'b', type: 'string'},
    ]);
  });

  test('flattens nested objects', () => {
    const obj = {
      user: {
        name: 'Alice',
        address: {
          city: 'Paris',
        },
      },
      age: 30,
    };

    expect(flattenObject(obj)).toEqual([
      {name: 'user.name', type: 'string'},
      {name: 'user.address.city', type: 'string'},
      {name: 'age', type: 'number'},
    ]);
  });

  test('handles arrays as leaf nodes', () => {
    const obj = {tags: ['a', 'b', 'c']};
    expect(flattenObject(obj)).toEqual([{name: 'tags', type: 'array'}]);
  });

  test('handles date objects', () => {
    const date = new Date();
    const obj = {created: date};
    expect(flattenObject(obj)).toEqual([{name: 'created', type: 'date'}]);
  });
});

describe('inferSchema', () => {
  test('infers schema from single object', () => {
    const data = {name: 'Alice', age: 30};
    expect(inferSchema(data)).toEqual([
      {name: 'name', type: 'string'},
      {name: 'age', type: 'number'},
    ]);
  });

  test('merges types from multiple objects', () => {
    const data = [
      {name: 'Alice', age: 30},
      {name: 'Bob', age: 'thirty'},
    ];

    expect(inferSchema(data)).toEqual([
      {name: 'name', type: 'string'},
      {name: 'age', type: 'number | string'},
    ]);
  });

  test('handles nested structures', () => {
    const data = [{user: {name: 'Alice'}}, {user: {age: 30}}];

    expect(inferSchema(data)).toEqual([
      {name: 'user.name', type: 'string'},
      {name: 'user.age', type: 'number'},
    ]);
  });

  test('handles empty input', () => {
    expect(inferSchema([])).toEqual([]);
    expect(inferSchema({})).toEqual([]);
  });

  test('handles mixed types including null/undefined', () => {
    const data = [
      {value: 42},
      {value: null},
      {value: 'text'},
      {value: undefined},
    ];

    expect(inferSchema(data)).toEqual([
      {name: 'value', type: 'number | null | string | undefined'},
    ]);
  });
});
