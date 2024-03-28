import {mapObject, ObjectPath} from './traverse';

describe('ObjectPath.toString', () => {
  it('handles empty path', () => {
    expect(new ObjectPath([]).toString()).toEqual('');
  });
  it('handles simple cases', () => {
    expect(new ObjectPath(['foo']).toString()).toEqual('foo');
    expect(new ObjectPath(['foo', 'bar']).toString()).toEqual('foo.bar');
  });
  it('escapes periods', () => {
    expect(new ObjectPath(['foo.bar.baz']).toString()).toEqual(
      'foo\\.bar\\.baz'
    );
  });
  it('escapes brackets', () => {
    expect(new ObjectPath(['foo[5]']).toString()).toEqual('foo\\[5\\]');
  });
});

describe('ObjectPath.parseString', () => {
  it('handles empty path', () => {
    expect(ObjectPath.parseString('')).toEqual([]);
  });
  it('handles simple cases', () => {
    expect(ObjectPath.parseString('foo')).toEqual(['foo']);
    expect(ObjectPath.parseString('foo.bar')).toEqual(['foo', 'bar']);
  });
  it('handles numeric keys', () => {
    expect(ObjectPath.parseString('0')).toEqual(['0']);
    expect(ObjectPath.parseString('42')).toEqual(['42']);
  });
  it('handles punctuation in keys', () => {
    expect(ObjectPath.parseString('a,b!')).toEqual(['a,b!']);
  });
  it('handles key access errors', () => {
    expect(() => {
      ObjectPath.parseString('.');
    }).toThrow();
    expect(() => {
      ObjectPath.parseString('a[0].');
    }).toThrow();
    expect(() => {
      ObjectPath.parseString('a..b');
    }).toThrow();
  });
  it('handles array index cases', () => {
    expect(ObjectPath.parseString('foo[2]')).toEqual(['foo', 2]);
    expect(ObjectPath.parseString('foo[2][3]')).toEqual(['foo', 2, 3]);
  });
  it('handles array index errors', () => {
    expect(() => {
      ObjectPath.parseString('foo[');
    }).toThrow();
    expect(() => {
      ObjectPath.parseString('foo[]');
    }).toThrow();
    expect(() => {
      ObjectPath.parseString('foo[1e3]');
    }).toThrow();
    expect(() => {
      ObjectPath.parseString('foo.[1]');
    }).toThrow();
  });
  it('handles escaped chars', () => {
    expect(ObjectPath.parseString('foo\\.bar')).toEqual(['foo.bar']);
    expect(ObjectPath.parseString('foo\\[')).toEqual(['foo[']);
  });
  it('handles escaping error', () => {
    expect(() => {
      ObjectPath.parseString('foo\\');
    }).toThrow();
  });
  it('handles complex cases', () => {
    expect(ObjectPath.parseString('fo\\.o[1].bar.baz.bim[3][5].wat')).toEqual([
      'fo.o',
      1,
      'bar',
      'baz',
      'bim',
      3,
      5,
      'wat',
    ]);
  });
});

describe('ObjectPath.apply', () => {
  const obj = {
    foo: 'bar',
    baz: [40, 41, 42, 43, 44],
    qux: {
      quux: 'quuz',
      quub: {
        quud: 'quul',
      },
    },
    arr: [
      99,
      {
        a: 'b',
      },
    ],
    'a.b': 'c',
  };
  it('handles basic cases', () => {
    expect(new ObjectPath('lol').apply(obj)).toBe(undefined);
    expect(new ObjectPath('foo').apply(obj)).toEqual('bar');
    expect(new ObjectPath('baz').apply(obj)).toEqual([40, 41, 42, 43, 44]);
    expect(new ObjectPath('qux.quux').apply(obj)).toEqual('quuz');
    expect(new ObjectPath('baz[2]').apply(obj)).toEqual(42);
    expect(new ObjectPath('baz[99]').apply(obj)).toBe(undefined);
    expect(new ObjectPath('arr[1].a').apply(obj)).toEqual('b');
  });
});

describe('ObjectPath.set', () => {
  it('can set an existing top-level key', () => {
    const obj = {
      foo: 'bar',
    };
    new ObjectPath('foo').set(obj, 'abc');
    expect(obj).toEqual({foo: 'abc'});
  });
  it('can set a non-existing top-level key', () => {
    const obj = {};
    new ObjectPath('bim').set(obj, 'baz');
    expect(obj).toEqual({bim: 'baz'});
  });
  it('can traverse nested objects', () => {
    const obj = {foo: {bar: {baz: 42}}};
    new ObjectPath('foo.bar.baz').set(obj, 19);
    expect(obj).toEqual({foo: {bar: {baz: 19}}});
  });
  it('can set an index within an array', () => {
    const obj = {
      foo: [10, 20, 30],
    };
    new ObjectPath('foo[1]').set(obj, 'abc');
    expect(obj).toEqual({foo: [10, 'abc', 30]});
  });
});

describe('mapObject', () => {
  it('can turn integers into strings', () => {
    const obj = {
      foo: [10, 20, 30],
      bar: {
        baz: 42,
      },
    };
    expect(
      mapObject(obj, context => {
        if (typeof context.value === 'number') {
          return context.value.toString();
        }
        return context.value;
      })
    ).toEqual({
      foo: ['10', '20', '30'],
      bar: {baz: '42'},
    });
  });
  it('can replace a deeply nested object', () => {
    const obj = {
      foo: {
        bar: {
          baz: 'findme',
        },
      },
    };
    expect(
      mapObject(obj, context => {
        if (context.value === 'findme') {
          return {found: true};
        }
        return context.value;
      })
    ).toEqual({
      foo: {
        bar: {
          baz: {found: true},
        },
      },
    });
  });
});
