import * as weave from 'weave';
import {getGlobalClient} from 'weave/clientApi';
import {Op} from 'weave/opType';

// Mock the client to capture callDisplayName
let capturedDisplayName: string | undefined;
jest.mock('weave/clientApi', () => ({
  getGlobalClient: jest.fn(() => ({
    pushNewCall: () => ({currentCall: {}, parentCall: null, newStack: []}),
    createCall: (...args: any[]) => {
      capturedDisplayName = args[8]; // 9th parameter (displayName)
      return Promise.resolve();
    },
    runWithCallStack: async (stack: any, fn: () => any) => fn(),
    finishCall: () => Promise.resolve(),
    finishCallWithException: () => Promise.resolve(),
    settings: {shouldPrintCallLink: false},
    waitForBatchProcessing: () => Promise.resolve(),
  })),
}));

describe('op legacy decorators', () => {
  beforeEach(() => {
    capturedDisplayName = undefined;
    (getGlobalClient as jest.Mock).mockClear();
  });

  it('works as a basic method decorator', async () => {
    class TestClass {
      private value: number;

      constructor(value: number) {
        this.value = value;
      }

      @weave.op
      async multiply(factor: number) {
        return this.value * factor;
      }
    }

    const instance = new TestClass(5);
    const result = await instance.multiply(3);
    expect(result).toBe(15);

    // Verify op properties were set correctly
    const opFn = instance.multiply as any;
    expect(opFn.__isOp).toBe(true);
    expect(opFn.__name).toBe('TestClass.multiply');
    expect(typeof opFn.__wrappedFunction).toBe('function');
  });

  it('works with static class methods', async () => {
    class MathOps {
      @weave.op
      static async square(x: number) {
        return x * x;
      }

      @weave.op({
        name: 'powerOp',
        callDisplayName: (...args: any[]) => `Computing ${args[0]}^${args[1]}`,
      })
      static async power(base: number, exponent: number) {
        return Math.pow(base, exponent);
      }
    }

    // Test basic functionality
    const squared = await MathOps.square(4);
    expect(squared).toBe(16);
    expect(capturedDisplayName).toBeUndefined();

    const powered = await MathOps.power(2, 3);
    expect(powered).toBe(8);
    expect(capturedDisplayName).toBe('Computing 2^3');

    // Verify op properties for basic decorator
    const squareFn = MathOps.square as unknown as Op<typeof MathOps.square>;
    expect(squareFn.__isOp).toBe(true);
    expect(squareFn.__name).toBe('MathOps.square');
    expect(typeof squareFn.__wrappedFunction).toBe('function');

    // Verify op properties for decorator with options
    const powerFn = MathOps.power as Op<any>;
    expect(powerFn.__isOp).toBe(true);
    expect(powerFn.__name).toBe('powerOp');
    expect(typeof powerFn.__wrappedFunction).toBe('function');
  });

  it('works as a decorator factory with options', async () => {
    class TestClass {
      private prefix: string;

      constructor(prefix: string) {
        this.prefix = prefix;
      }

      @weave.op({
        name: 'customOpName',
        callDisplayName: (...args: any[]) => `Processing: ${args[0]}`,
        parameterNames: ['inputText'],
      })
      async addPrefix(text: string) {
        return this.prefix + text;
      }
    }

    const instance = new TestClass('Hello-');
    const result = await instance.addPrefix('World');
    expect(result).toBe('Hello-World');
    expect(capturedDisplayName).toBe('Processing: World');

    // Verify op properties and options were set correctly
    const opFn = instance.addPrefix as any;
    expect(opFn.__isOp).toBe(true);
    expect(opFn.__name).toBe('customOpName');
    expect(typeof opFn.__wrappedFunction).toBe('function');
  });

  it('maintains correct this binding in decorated methods', async () => {
    class TestClass {
      private multiplier: number;

      constructor() {
        this.multiplier = 2;
      }

      @weave.op({
        name: 'multiplyAndAdd',
      })
      async calculate(value: number, addend: number) {
        return value * this.multiplier + addend;
      }
    }

    const instance = new TestClass();
    const result = await instance.calculate(5, 3);
    expect(result).toBe(13); // (5 * 2) + 3
  });
});
