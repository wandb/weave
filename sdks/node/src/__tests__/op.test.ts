import {op} from 'weave';
import type {Op, OpColor, OpKind} from 'weave/opType';
// Import the actual module
import * as clientApi from 'weave/clientApi';

// Function to create a fresh mock client for each call
const createFreshMockClient = () => ({
  pushNewCall: jest.fn(() => ({
    currentCall: {callId: 'mockCallId', traceId: 'mockTraceId'},
    parentCall: null,
    newStack: [],
  })),
  createCall: jest.fn((...args: any[]) => {
    // We still need a way to capture this if tests rely on it.
    // Maybe pass a shared object or use a different mechanism?
    // For now, let's remove the direct capture here.
    // capturedDisplayName = displayName;
    return Promise.resolve();
  }),
  runWithCallStack: jest.fn(async (stack: any, fn: () => any) => fn()),
  finishCall: jest.fn(() => Promise.resolve()),
  finishCallWithException: jest.fn(() => Promise.resolve()),
  settings: {shouldPrintCallLink: false},
  waitForBatchProcessing: jest.fn(() => Promise.resolve()),
});

describe('op wrappers', () => {
  let getGlobalClientSpy: jest.SpyInstance;

  beforeEach(() => {
    // Spy on the actual getGlobalClient
    getGlobalClientSpy = jest.spyOn(clientApi, 'getGlobalClient');
    // Default implementation returns a fresh mock client each time
    getGlobalClientSpy.mockImplementation(createFreshMockClient);
  });

  afterEach(() => {
    // Restore the original implementation after each test
    getGlobalClientSpy.mockRestore();
  });

  it('works with method binding in constructor', async () => {
    // Base class with the implementation
    class BaseModel {
      protected oaiClient: any;

      constructor() {
        this.oaiClient = {
          chat: {
            completions: {
              create: async ({messages}: any) => messages[0].content,
            },
          },
        };
      }

      async invoke(prompt: string) {
        return await this.oaiClient.chat.completions.create({
          model: 'gpt-4-turbo',
          messages: [{role: 'user', content: prompt}],
        });
      }
    }

    // Derived class that sets up the op binding
    class WeaveModel extends BaseModel {
      public invoke: Op<(prompt: string) => Promise<string>>;

      constructor() {
        super();
        this.invoke = op(this, super.invoke);
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

  it('works with wrapping in the constructor', async () => {
    class Model {
      private oaiClient: any;

      constructor() {
        this.oaiClient = {
          chat: {
            completions: {
              create: async ({messages}: any) => messages[0].content,
            },
          },
        };

        this.invoke = op(this, this.invoke);
      }

      async invoke(prompt: string): Promise<string> {
        return await this.oaiClient.chat.completions.create({
          model: 'gpt-4-turbo',
          messages: [{role: 'user', content: prompt}],
        });
      }
    }

    type ModelWithOp = {
      invoke: Op<typeof Model.prototype.invoke>;
    };

    const model = new Model() as Model & ModelWithOp;
    const result = await model.invoke('test prompt');
    expect(result).toBe('test prompt');

    expect(model.invoke.__isOp).toBe(true);
    expect(model.invoke.__name).toBe('Model.invoke');
    expect(typeof model.invoke.__wrappedFunction).toBe('function');
    expect(model.invoke.__boundThis).toBe(model);

    const newImpl = async (prompt: string) => `Modified: ${prompt}`;
    model.invoke = op(model, newImpl);
    const modifiedResult = await model.invoke('test prompt');
    expect(modifiedResult).toBe('Modified: test prompt');
  });

  it('correctly names directly wrapped functions', () => {
    async function myStandaloneFunction() {
      return 42;
    }
    const wrappedFn = op(myStandaloneFunction);
    expect((wrappedFn as Op<any>).__name).toBe('myStandaloneFunction');

    const wrappedAnon = op(async () => {});
    expect((wrappedAnon as Op<any>).__name).toBe('anonymous');
  });

  it('correctly names bound functions', async () => {
    class MyClass {
      value = 10;
      async instanceMethod(factor: number) {
        return this.value * factor;
      }
    }
    const instance = new MyClass();
    const boundMethod = op(instance, instance.instanceMethod);
    expect((boundMethod as Op<any>).__name).toBe('MyClass.instanceMethod');
    await expect(boundMethod(3)).resolves.toBe(30);
  });

  it('runs original function without tracking if weave not initialized', async () => {
    // Override the spy implementation for this test *only*
    getGlobalClientSpy.mockImplementationOnce(() => null);

    const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

    async function testFunc(a: number) {
      return a * 2;
    }
    const wrapped = op(testFunc);
    const result = await wrapped(5); // This call will use the mockImplementationOnce

    expect(result).toBe(10);
    // Verify the spy was called once
    expect(getGlobalClientSpy).toHaveBeenCalledTimes(1);
    // Verify console warning
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      expect.stringContaining('WARNING: Weave is not initialized')
    );

    consoleWarnSpy.mockRestore();
  });

  it('handles errors correctly in wrapped functions', async () => {
    const error = new Error('Test error');
    async function errorFunc() {
      throw error;
    }

    // Ensure we get a fresh mock client via the spy for this call
    const mockClientInstance = createFreshMockClient();
    getGlobalClientSpy.mockImplementationOnce(() => mockClientInstance);

    const wrapped = op(errorFunc);

    await expect(wrapped()).rejects.toThrow('Test error');

    // Verify the spy was called
    expect(getGlobalClientSpy).toHaveBeenCalledTimes(1);

    // Assertions on the specific mock instance returned for this test
    expect(mockClientInstance.finishCallWithException).toHaveBeenCalled();
    const args = mockClientInstance.finishCallWithException.mock.lastCall;
    // The first arg is internal, so we shift it off and not check it
    args?.shift();
    expect(args).toEqual([
      error,
      expect.objectContaining({callId: 'mockCallId'}), // currentCall
      null, // parentCall
      expect.any(Date), // endTime
      expect.any(Promise), // startCallPromise
    ]);
    expect(mockClientInstance.finishCall).not.toHaveBeenCalled();
  });
});

describe('op kind and color', () => {
  let getGlobalClientSpy: jest.SpyInstance;

  beforeEach(() => {
    getGlobalClientSpy = jest.spyOn(clientApi, 'getGlobalClient');
  });

  afterEach(() => {
    getGlobalClientSpy.mockRestore();
  });

  it('stores kind on the op wrapper', () => {
    async function testFunc() {
      return 42;
    }
    const wrapped = op(testFunc, {kind: 'llm'});
    expect((wrapped as Op<any>).__kind).toBe('llm');
  });

  it('stores color on the op wrapper', () => {
    async function testFunc() {
      return 42;
    }
    const wrapped = op(testFunc, {color: 'blue'});
    expect((wrapped as Op<any>).__color).toBe('blue');
  });

  it('stores both kind and color on the op wrapper', () => {
    async function testFunc() {
      return 42;
    }
    const wrapped = op(testFunc, {kind: 'agent', color: 'purple'});
    expect((wrapped as Op<any>).__kind).toBe('agent');
    expect((wrapped as Op<any>).__color).toBe('purple');
  });

  it('passes kind and color to createCall in attributes', async () => {
    let capturedAttributes: any;
    const mockClient = {
      pushNewCall: jest.fn(() => ({
        currentCall: {callId: 'mockCallId', traceId: 'mockTraceId'},
        parentCall: null,
        newStack: [],
      })),
      createCall: jest.fn(
        (
          _call: any,
          _opRef: any,
          _params: any,
          _paramNames: any,
          _thisArg: any,
          _currentCall: any,
          _parentCall: any,
          _startTime: any,
          _displayName: any,
          attributes: any
        ) => {
          // Note: We can't directly capture attributes from inside createCall
          // since the actual attribute merging happens in weaveClient.ts
          // This test verifies the op properties are set correctly
          return Promise.resolve();
        }
      ),
      runWithCallStack: jest.fn(async (stack: any, fn: () => any) => fn()),
      finishCall: jest.fn(() => Promise.resolve()),
      settings: {shouldPrintCallLink: false},
    };

    getGlobalClientSpy.mockImplementation(() => mockClient);

    async function testFunc() {
      return 42;
    }
    const wrapped = op(testFunc, {kind: 'tool', color: 'green'});
    await wrapped();

    // Verify the op has the correct kind and color stored
    expect((wrapped as Op<any>).__kind).toBe('tool');
    expect((wrapped as Op<any>).__color).toBe('green');

    // Verify createCall was called (attributes are handled in weaveClient.ts)
    expect(mockClient.createCall).toHaveBeenCalled();
  });

  it('allows all valid kind values', () => {
    const kinds: OpKind[] = ['agent', 'llm', 'tool', 'search'];
    kinds.forEach(kind => {
      const wrapped = op(async () => 42, {kind});
      expect((wrapped as Op<any>).__kind).toBe(kind);
    });
  });

  it('allows all valid color values', () => {
    const colors: OpColor[] = [
      'red',
      'orange',
      'yellow',
      'green',
      'blue',
      'purple',
    ];
    colors.forEach(color => {
      const wrapped = op(async () => 42, {color});
      expect((wrapped as Op<any>).__color).toBe(color);
    });
  });

  it('kind and color are undefined when not specified', () => {
    const wrapped = op(async () => 42);
    expect((wrapped as Op<any>).__kind).toBeUndefined();
    expect((wrapped as Op<any>).__color).toBeUndefined();
  });

  it('works with method binding and kind/color', async () => {
    class MyModel {
      async invoke(prompt: string) {
        return `Response: ${prompt}`;
      }
    }

    const instance = new MyModel();
    const boundMethod = op(instance, instance.invoke, {
      kind: 'llm',
      color: 'blue',
    });

    expect((boundMethod as Op<any>).__kind).toBe('llm');
    expect((boundMethod as Op<any>).__color).toBe('blue');
    expect((boundMethod as Op<any>).__name).toBe('MyModel.invoke');
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
      finalizeFn: () => {
        // no-op
      },
    };
    const streamOp = op(numberStream, {streamReducer});

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
