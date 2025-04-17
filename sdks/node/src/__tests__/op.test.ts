import * as weave from 'weave';
import type {Op} from '../opType';
import {getGlobalClient} from '../clientApi';

// Mock the client to capture callDisplayName
let capturedDisplayName: string | undefined;
jest.mock('../clientApi', () => ({
  getGlobalClient: jest.fn(() => ({
    pushNewCall: () => ({currentCall: {}, parentCall: null, newStack: []}),
    createCall: (_: any, __: any, ___: any, ____: any, _____: any, ______: any, _______: any, displayName: string) => {
      capturedDisplayName = displayName;
      return Promise.resolve();
    },
    runWithCallStack: async (stack: any, fn: () => any) => fn(),
    finishCall: () => Promise.resolve(),
    finishCallWithException: () => Promise.resolve(),
    settings: {shouldPrintCallLink: false},
    waitForBatchProcessing: () => Promise.resolve()
  }))
}));

describe('op decorators', () => {
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

  it('works with function wrapping for standalone functions', async () => {
    // For standalone functions, we need to use the function wrapper form
    const add = weave.op(async (a: number, b: number) => {
      return a + b;
    });

    const multiply = weave.op(async (a: number, b: number) => {
      return a * b;
    }, {
      name: 'customMultiply',
      callDisplayName: (...args: any[]) => `Multiplying ${args[0]} * ${args[1]}`
    });

    const sum = await add(5, 3);
    expect(sum).toBe(8);
    expect(capturedDisplayName).toBeUndefined();

    const product = await multiply(4, 2);
    expect(product).toBe(8);
    expect(capturedDisplayName).toBe('Multiplying 4 * 2');

    // Verify op properties
    expect((add as Op<any>).__isOp).toBe(true);
    expect((add as Op<any>).__name).toBe('anonymous');
    expect(typeof (add as Op<any>).__wrappedFunction).toBe('function');

    expect((multiply as Op<any>).__isOp).toBe(true);
    expect((multiply as Op<any>).__name).toBe('customMultiply');
  });

  it('works with static class methods', async () => {
    class MathOps {
      @weave.op
      static async square(x: number) {
        return x * x;
      }

      @weave.op({
        name: 'powerOp',
        callDisplayName: (...args: any[]) => `Computing ${args[0]}^${args[1]}`
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

    // Verify that static methods don't have 'this' binding
    expect(await MathOps.square.call(null, 5)).toBe(25);
    expect(await MathOps.power.call(null, 2, 4)).toBe(16);
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
        parameterNames: ['inputText']
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
        name: 'multiplyAndAdd'
      })
      async calculate(value: number, addend: number) {
        return (value * this.multiplier) + addend;
      }
    }

    const instance = new TestClass();
    const result = await instance.calculate(5, 3);
    expect(result).toBe(13); // (5 * 2) + 3
  });

  it('works with method binding in constructor', async () => {
    // Base class with the implementation
    class BaseModel {
      protected oaiClient: any;

      constructor() {
        this.oaiClient = {
          chat: {
            completions: {
              create: async ({ messages }: any) => messages[0].content
            }
          }
        };
      }

      async invoke(prompt: string) {
        return await this.oaiClient.chat.completions.create({
          model: 'gpt-4-turbo',
          messages: [{ role: 'user', content: prompt }],
        });
      }
    }

    // Derived class that sets up the op binding
    class WeaveModel extends BaseModel {
      public invoke: Op<(prompt: string) => Promise<string>>;

      constructor() {
        super();
        this.invoke = weave.op(this, super.invoke);
      }
    }

    const model = new WeaveModel();
    const result = await model.invoke('test prompt');
    expect(result).toBe('test prompt');

    // Verify op properties were set correctly
    expect((model.invoke as Op<any>).__isOp).toBe(true);
    expect((model.invoke as Op<any>).__name).toBe('WeaveModel.invoke');
    expect(typeof (model.invoke as Op<any>).__wrappedFunction).toBe('function');
    expect((model.invoke as Op<any>).__boundThis).toBe(model);
  });

  it('works with getOwnPropertyDescriptor in constructor', async () => {
    class Model {
      private oaiClient: any;

      constructor() {
        this.oaiClient = {
          chat: {
            completions: {
              create: async ({ messages }: any) => messages[0].content
            }
          }
        };

        // Get the original method descriptor from the prototype and wrap it
        const descriptor = Object.getOwnPropertyDescriptor(Model.prototype, 'invoke')!;
        this.invoke = weave.op(this, descriptor.value);
      }

      async invoke(prompt: string): Promise<string> {
        return await this.oaiClient.chat.completions.create({
          model: 'gpt-4-turbo',
          messages: [{ role: 'user', content: prompt }],
        });
      }
    }

    type ModelWithOp = {
      invoke: Op<typeof Model.prototype.invoke>;
    };

    const model = new Model() as Model & ModelWithOp;
    const result = await model.invoke('test prompt');
    expect(result).toBe('test prompt');

    // Verify op properties were set correctly
    expect(model.invoke.__isOp).toBe(true);
    expect(model.invoke.__name).toBe('Model.invoke');
    expect(typeof model.invoke.__wrappedFunction).toBe('function');
    expect(model.invoke.__boundThis).toBe(model);

    // Verify we can still reassign if needed (matches original descriptor behavior)
    const newImpl = async (prompt: string) => `Modified: ${prompt}`;
    model.invoke = weave.op(model, newImpl);
    const modifiedResult = await model.invoke('test prompt');
    expect(modifiedResult).toBe('Modified: test prompt');
  });
});

describe('op streaming', () => {
  it('maintains isolated state for concurrent streams', async () => {
    // Simple stream that emits numbers with some delay to ensure interleaving
    async function* numberStream(id: string, nums: number[]) {
      const startTime = Date.now();
      for (const n of nums) {
        const sleepTime = Math.floor(Math.random() * 40) + 10;
        await new Promise(resolve => setTimeout(resolve, sleepTime));
        yield {id, value: n, time: Date.now() - startTime};
      }
    }

    // Create an op with a summing stream reducer
    const streamReducer = {
      initialStateFn: () => ({sum: 0, id: ''}),
      reduceFn: (state: any, chunk: any) => ({
        sum: state.sum + chunk.value,
        id: chunk.id,
      }),
    };
    const streamOp = weave.op(numberStream, {streamReducer});

    // Define a few streams to run concurrently
    const testCases = [
      {id: 'a', numbers: [1, 2, 3, 4, 5], expectedSum: 15},
      {id: 'b', numbers: [10, 20, 30, 40, 50], expectedSum: 150},
      {id: 'c', numbers: [100, 200, 300, 400, 500], expectedSum: 1500},
      {id: 'd', numbers: [1000, 2000, 3000, 4000, 5000], expectedSum: 15000},
      {id: 'e', numbers: [2, 4, 6, 8, 10], expectedSum: 30},
    ];

    // Store chunks and states for each stream
    const results = testCases.map(() => ({
      times: [] as number[],
      chunks: [] as any[],
      finalState: streamReducer.initialStateFn(),
    }));

    // Run all streams concurrently
    const startTime = Date.now();
    await Promise.all(
      testCases.map(async (testCase, index) => {
        const stream = await streamOp(testCase.id, testCase.numbers);
        for await (const chunk of stream) {
          results[index].times.push(Date.now() - startTime);
          results[index].chunks.push(chunk);
        }
      })
    );

    // Verify concurrency by checking that we received chunks from different streams
    // within a small time window
    const allTimes = results
      .flatMap((result, idx) =>
        result.times.map(time => ({time, streamIndex: idx}))
      )
      .sort((a, b) => a.time - b.time);

    // Check that within the first N chunks, we see at least 3 different streams
    const firstNChunks = allTimes.slice(0, 5);
    const uniqueStreamsEarly = new Set(firstNChunks.map(x => x.streamIndex))
      .size;
    expect(uniqueStreamsEarly).toBeGreaterThanOrEqual(3);

    // Verify results for each stream
    testCases.forEach((testCase, index) => {
      // Collect just the chunk data (don't need the time)
      const chunksWithoutTime = results[index].chunks.map(({id, value}) => ({
        id,
        value,
      }));
      expect(chunksWithoutTime).toEqual(
        testCase.numbers.map(value => ({
          id: testCase.id,
          value,
        }))
      );

      // Reduce chunks and confirm final state is as we expect
      results[index].chunks.forEach(chunk => {
        results[index].finalState = streamReducer.reduceFn(
          results[index].finalState,
          chunk
        );
      });
      expect(results[index].finalState).toEqual({
        sum: testCase.expectedSum,
        id: testCase.id,
      });
    });
  });
});
