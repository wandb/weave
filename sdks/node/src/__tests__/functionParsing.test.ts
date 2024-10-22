import { inferFunctionArguments, invoke } from '../fn';

function example(a: number, b: number, c: number) {
  return a * b + c;
}
const row = { x: 1, y: 2, z: 3 };
const missingRow = { y: 2, z: 3 };
const mapping = { z: 'a', y: 'b', x: 'c' };
const missingMapping = { z: 'a', y: 'b' };

describe('Functions', () => {
  test('invoke with mapping', async () => {
    const res = invoke(example, row, mapping);
    expect(res).toEqual(7);
  });

  test('invoke with missing arguments', async () => {
    expect(() => invoke(example, row, missingMapping)).toThrow('Missing required argument');
    expect(() => invoke(example, missingRow, mapping)).toThrow('Missing required argument');
    expect(() => invoke(example, missingRow, missingMapping)).toThrow('Missing required argument');
  });
});

function basic(
  a: number,
  b: number, // comment
  c: number = 3
) {
  return a * b + c;
}

function basicRest(a: number, b: number, ...rest: number[]) {
  return a * b + rest.reduce((acc, v) => acc + v, 0);
}

function basicDestructuringOneObj({
  a,
  b,
  c = 3,
}: {
  a: number;
  b: number; //comment
  c?: number;
}) {
  return a * b + c;
}

function basicDestructuringMultipleObj(
  {
    a,
    b,
  }: {
    a: number;
    b: number; //comment
  },
  {
    c = 3,
  }: {
    c?: number;
  }
) {
  return a * b + c;
}

function basicDestructuringArray([
  a,
  b, //comment
  c,
]: [number, number, number]) {
  return a * b + c;
}

function basicDestructuringArrayMultiple(
  [
    a,
    b, //comment
  ]: [number, number],
  [c]: [number]
) {
  return a * b + c;
}

const arrow = (
  a: number,
  b: number, // comment
  c: number = 3
) => a * b + c;
const funcExpr = function (
  a: number,
  b: number, // comment
  c: number = 3
) {
  return a * b + c;
};
const generator = function* (
  a: number,
  b: number, // comment
  c: number = 3
) {
  yield a;
  yield b;
  yield c;
};

async function basicAsync(
  a: number,
  b: number, // comment
  c: number = 3
) {
  return a * b + c;
}
const arrowAsync = async (
  a: number,
  b: number, // comment
  c: number = 3
) => a * b + c;
const funcExprAsync = async function (
  a: number,
  b: number, // comment
  c: number = 3
) {
  return a * b + c;
};
const generatorAsync = async function* (
  a: number,
  b: number, // comment
  c: number = 3
) {
  yield a;
  yield b;
  yield c;
};

class Example {
  method(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    return a * b + c;
  }
  async asyncMethod(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    return a * b + c;
  }
  *generator(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    yield a;
    yield b;
    yield c;
  }
  async *asyncGenerator(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    yield a;
    yield b;
    yield c;
  }
  static staticMethod(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    return a * b + c;
  }
  static async staticAsyncMethod(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    return a * b + c;
  }
  static *staticGenerator(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    yield a;
    yield b;
    yield c;
  }
  static async *staticAsyncGenerator(
    a: number,
    b: number, // comment
    c: number = 3
  ) {
    yield a;
    yield b;
    yield c;
  }
}

const expectedArgs = { a: undefined, b: undefined, c: '3' };

describe('Function parsing', () => {
  const testCases = [
    { name: 'basic', func: basic },
    { name: 'arrow', func: arrow },
    { name: 'function expression', func: funcExpr },
    { name: 'async basic', func: basicAsync },
    { name: 'async arrow', func: arrowAsync },
    { name: 'async function expression', func: funcExprAsync },
    { name: 'class method', func: new Example().method },
    { name: 'class async method', func: new Example().asyncMethod },
    { name: 'class static method', func: Example.staticMethod },
    { name: 'class static async method', func: Example.staticAsyncMethod },
    { name: 'class generator', func: new Example().generator },
    { name: 'class async generator', func: new Example().asyncGenerator },
    { name: 'class static generator', func: Example.staticGenerator },
    { name: 'class static async generator', func: Example.staticAsyncGenerator },
    { name: 'basic destructuring -- 1 arg', func: basicDestructuringOneObj },

    // These don't work yet
    { skip: true, name: 'basic destructuring -- multiple args', func: basicDestructuringMultipleObj },
    { skip: true, name: 'basic destructuring -- array', func: basicDestructuringArray },
    { skip: true, name: 'basic destructuring -- array multiple', func: basicDestructuringArrayMultiple },
  ];

  testCases.forEach(({ name, func, skip }) => {
    if (skip) {
      test.skip(name, () => {});
    } else {
      test(name, () => {
        const args = inferFunctionArguments(func);
        expect(args).toEqual(expectedArgs);
      });
    }
  });
  test.skip('basic rest', () => {
    const args = inferFunctionArguments(basicRest);
    expect(args).toEqual({ a: undefined, b: undefined, rest: '[]' });
  });
});
