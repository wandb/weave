import {InMemoryTraceServer} from '../../inMemoryTraceServer';
import {commonPatchAnthropic} from '../../integrations/anthropic';
import {initWithCustomTraceServer} from '../clientMock';

// Helper function to get calls
async function getCalls(traceServer: InMemoryTraceServer, projectId: string) {
  const calls = await traceServer.calls
    .callsStreamQueryPost({
      project_id: projectId,
      limit: 100,
    })
    .then(result => result.calls);
  return calls;
}

// Mock Anthropic SDK
function createMockAnthropic() {
  const mockMessages = {
    id: 'msg_123',
    role: 'assistant',
    type: 'message',
    model: 'claude-3-opus-20240229',
    content: [{type: 'text', text: 'Hello! How can I help you today?'}],
    stop_reason: 'end_turn',
    stop_sequence: null,
    usage: {
      input_tokens: 10,
      output_tokens: 8,
    },
  };

  const mockStreamChunks = [
    {
      type: 'message_start',
      message: {
        id: 'msg_123',
        role: 'assistant',
        type: 'message',
        model: 'claude-3-opus-20240229',
        content: [],
        stop_reason: null,
        stop_sequence: null,
        usage: {input_tokens: 10, output_tokens: 0},
      },
    },
    {
      type: 'content_block_start',
      index: 0,
      content_block: {type: 'text', text: 'Hello! How can I help you today?'},
    },
    {
      type: 'content_block_stop',
      index: 0,
    },
    {
      type: 'message_delta',
      delta: {stop_reason: 'end_turn', stop_sequence: null},
      usage: {output_tokens: 8},
    },
    {
      type: 'message_stop',
    },
  ];

  const mockBatchResult = {
    id: 'batch_123',
    type: 'message_batch',
    processing_status: 'ended',
    request_counts: {
      processing: 0,
      succeeded: 1,
      errored: 0,
      canceled: 0,
      expired: 0,
    },
    ended_at: '2024-01-01T00:00:00.000Z',
    created_at: '2024-01-01T00:00:00.000Z',
    expires_at: '2024-01-02T00:00:00.000Z',
    cancel_initiated_at: null,
    results_url:
      'https://api.anthropic.com/v1/messages/batches/batch_123/results',
  };

  const mockBatchResultsChunks = [
    {
      type: undefined,
      custom_id: 'request_1',
      result: {
        type: 'message',
        message: mockMessages,
      },
    },
  ];

  class MockAnthropicStream {
    private chunks: any[];
    private currentIndex = 0;
    public messages: any[] = [];

    constructor(chunks: any[]) {
      this.chunks = chunks;
    }

    async *[Symbol.asyncIterator]() {
      for (const chunk of this.chunks) {
        yield chunk;
      }
    }

    on(event: string, callback: Function) {
      if (event === 'end') {
        // Simulate end event after processing all chunks
        setTimeout(() => {
          // Simulate the final messages state
          this.messages = [
            {
              id: 'msg_123',
              role: 'assistant',
              type: 'message',
              model: 'claude-3-opus-20240229',
              content: [
                {type: 'text', text: 'Hello! How can I help you today?'},
              ],
              stop_reason: 'end_turn',
              stop_sequence: null,
              usage: {input_tokens: 10, output_tokens: 8},
            },
          ];
          callback();
        }, 100);
      } else if (event === 'error') {
        // Just store the error callback for potential use
        this.errorCallback = callback;
      }
      return this;
    }

    private errorCallback?: Function;
  }

  // Create mock constructor functions
  function MockMessages() {
    // Constructor function
  }

  // Create a Promise-like object that CAN be monkey-patched
  class MockAPIPromise {
    private promise: Promise<any>;

    constructor(value: any) {
      this.promise = Promise.resolve(value);
    }

    then(onFulfilled?: any, onRejected?: any) {
      return this.promise.then(onFulfilled, onRejected);
    }

    catch(onRejected?: any) {
      return this.promise.catch(onRejected);
    }

    finally(onFinally?: any) {
      return this.promise.finally(onFinally);
    }
  }

  MockMessages.prototype.create = jest
    .fn()
    .mockImplementation((options: any) => {
      if (options.stream) {
        const stream = new MockAnthropicStream(mockStreamChunks);
        return new MockAPIPromise(stream);
      }
      return new MockAPIPromise(mockMessages);
    });

  MockMessages.prototype.stream = jest
    .fn()
    .mockImplementation((options: any) => {
      return new MockAnthropicStream(mockStreamChunks);
    });

  function MockBatches() {
    // Constructor function
  }

  MockBatches.prototype.create = jest.fn().mockResolvedValue(mockBatchResult);
  MockBatches.prototype.retrieve = jest.fn().mockResolvedValue(mockBatchResult);
  MockBatches.prototype.results = jest.fn().mockImplementation(async () => {
    return new MockAnthropicStream(mockBatchResultsChunks);
  });

  // Set up static reference
  MockMessages.Batches = MockBatches;

  const mockAnthropic = {
    Anthropic: {
      Messages: MockMessages,
    },
  };

  return {mockAnthropic, MockMessages, MockBatches};
}

describe('Anthropic Integration', () => {
  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';
  let mockAnthropic: any;
  let MockMessages: any;
  let MockBatches: any;
  let patchedAnthropic: any;

  beforeEach(() => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);

    const mockData = createMockAnthropic();
    mockAnthropic = mockData.mockAnthropic;
    MockMessages = mockData.MockMessages;
    MockBatches = mockData.MockBatches;

    // Apply patching
    patchedAnthropic = commonPatchAnthropic(mockAnthropic);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('non-streaming message creation', async () => {
    const messages = [{role: 'user', content: 'Hello, Claude!'}];
    const options = {
      model: 'claude-3-opus-20240229',
      max_tokens: 100,
      messages,
    };

    // Create instance and call create
    const anthropic = new patchedAnthropic.Anthropic.Messages();
    const result = await anthropic.create(options);

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check results
    expect(result).toMatchObject({
      id: 'msg_123',
      role: 'assistant',
      type: 'message',
      model: 'claude-3-opus-20240229',
      content: [{type: 'text', text: 'Hello! How can I help you today?'}],
      stop_reason: 'end_turn',
      usage: {
        input_tokens: 10,
        output_tokens: 8,
      },
    });

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('create');
    expect(calls[0].inputs).toEqual({arg0: options, self: {}});
    expect(calls[0].output).toMatchObject(result);
    expect(calls[0].summary).toEqual({
      usage: {
        'claude-3-opus-20240229': {
          input_tokens: 10,
          output_tokens: 8,
          requests: 1,
        },
      },
    });
  });

  test('streaming message creation', async () => {
    const messages = [{role: 'user', content: 'Hello, streaming Claude!'}];
    const options = {
      model: 'claude-3-opus-20240229',
      max_tokens: 100,
      messages,
      stream: true,
    };

    // Create instance and call create with streaming
    const anthropic = new patchedAnthropic.Anthropic.Messages();
    const stream = await anthropic.create(options);

    let collectedText = '';
    for await (const chunk of stream) {
      if (chunk.type === 'content_block_start' && chunk.content_block?.text) {
        collectedText += chunk.content_block.text;
      }
    }

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check results
    expect(collectedText).toBe('Hello! How can I help you today?');

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('create');
    expect(calls[0].inputs).toEqual({arg0: options, self: {}});

    // Now that we use MockAPIPromise (which can be monkey-patched), the WeaveIterator works properly
    expect(calls[0].output).toMatchObject({
      messages: expect.arrayContaining([
        expect.objectContaining({
          id: 'msg_123',
          role: 'assistant',
          type: 'message',
          model: 'claude-3-opus-20240229',
          content: expect.arrayContaining([
            expect.objectContaining({
              type: 'text',
              text: 'Hello! How can I help you today?',
            }),
          ]),
          stop_reason: 'end_turn',
          usage: {
            input_tokens: 10,
            output_tokens: 8,
          },
        }),
      ]),
    });

    expect(calls[0].summary).toEqual({
      usage: {
        'claude-3-opus-20240229': {
          input_tokens: 10,
          output_tokens: 8,
          requests: 1,
        },
      },
    });
  });

  test('stream helper method', async () => {
    const messages = [{role: 'user', content: 'Hello, stream helper!'}];
    const options = {
      model: 'claude-3-opus-20240229',
      max_tokens: 100,
      messages,
    };

    // Create instance and call stream
    const anthropic = new patchedAnthropic.Anthropic.Messages();
    const stream = await anthropic.stream(options);

    let collectedText = '';
    for await (const chunk of stream) {
      if (chunk.type === 'content_block_start' && chunk.content_block?.text) {
        collectedText += chunk.content_block.text;
      }
    }

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check results
    expect(collectedText).toBe('Hello! How can I help you today?');

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('stream');
    expect(calls[0].inputs).toMatchObject({arg1: options, self: {}});
    expect(calls[0].output).toMatchObject({
      messages: expect.arrayContaining([
        expect.objectContaining({
          id: 'msg_123',
          role: 'assistant',
          type: 'message',
          model: 'claude-3-opus-20240229',
        }),
      ]),
    });
    expect(calls[0].summary).toEqual({
      usage: {
        'claude-3-opus-20240229': {
          input_tokens: 10,
          output_tokens: 8,
          requests: 1,
        },
      },
    });
  });

  test('batch create operation', async () => {
    const batchOptions = {
      requests: [
        {
          custom_id: 'request_1',
          params: {
            model: 'claude-3-opus-20240229',
            max_tokens: 100,
            messages: [{role: 'user', content: 'Hello, batch!'}],
          },
        },
      ],
    };

    // Create instance and call batch create
    const batches = new patchedAnthropic.Anthropic.Messages.Batches();
    const result = await batches.create(batchOptions);

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check results
    expect(result).toMatchObject({
      id: 'batch_123',
      type: 'message_batch',
      processing_status: 'ended',
    });

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('create');
    expect(calls[0].inputs).toEqual({arg0: batchOptions, self: {}});
    expect(calls[0].output).toMatchObject(result);
  });

  test('batch retrieve operation', async () => {
    const batchId = 'batch_123';

    // Create instance and call batch retrieve
    const batches = new patchedAnthropic.Anthropic.Messages.Batches();
    const result = await batches.retrieve(batchId);

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check results
    expect(result).toMatchObject({
      id: 'batch_123',
      type: 'message_batch',
      processing_status: 'ended',
    });

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('retrieve');
    expect(calls[0].inputs).toEqual({arg0: batchId, self: {}});
    expect(calls[0].output).toMatchObject(result);
  });

  test('batch results operation', async () => {
    const batchId = 'batch_123';

    // Create instance and call batch results
    const batches = new patchedAnthropic.Anthropic.Messages.Batches();
    const stream = await batches.results(batchId);

    let resultCount = 0;
    for await (const chunk of stream) {
      if (chunk.custom_id) {
        resultCount++;
        expect(chunk.custom_id).toBe('request_1');
        expect(chunk.result.type).toBe('message');
        expect(chunk.result.message).toMatchObject({
          id: 'msg_123',
          role: 'assistant',
          type: 'message',
          model: 'claude-3-opus-20240229',
        });
      }
    }

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check results
    expect(resultCount).toBe(1);

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('results');
    expect(calls[0].inputs).toEqual({arg0: batchId, self: {}});
    expect(calls[0].output).toMatchObject({
      messages: expect.arrayContaining([
        expect.objectContaining({
          id: 'msg_123',
          role: 'assistant',
          type: 'message',
          model: 'claude-3-opus-20240229',
        }),
      ]),
    });
    expect(calls[0].summary).toEqual({
      usage: {
        'claude-3-opus-20240229': {
          input_tokens: 10,
          output_tokens: 8,
          requests: 1,
        },
      },
    });
  });

  test('error handling in non-streaming mode', async () => {
    const messages = [{role: 'user', content: 'This will fail'}];
    const options = {
      model: 'claude-3-opus-20240229',
      max_tokens: 100,
      messages,
    };

    // Mock an error
    MockMessages.prototype.create.mockRejectedValueOnce(new Error('API Error'));

    // Create instance and call create
    const anthropic = new patchedAnthropic.Anthropic.Messages();

    await expect(anthropic.create(options)).rejects.toThrow('API Error');

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('create');
    expect(calls[0].inputs).toEqual({arg0: options, self: {}});
    expect(calls[0].exception).toContain('API Error');
  });

  test('usage summarization with multiple models', async () => {
    const messages1 = [{role: 'user', content: 'Hello, Claude!'}];
    const messages2 = [{role: 'user', content: 'Hello, Haiku!'}];

    const options1 = {
      model: 'claude-3-opus-20240229',
      max_tokens: 100,
      messages: messages1,
    };

    const options2 = {
      model: 'claude-3-haiku-20240307',
      max_tokens: 100,
      messages: messages2,
    };

    // Mock different responses for different models
    MockMessages.prototype.create
      .mockResolvedValueOnce({
        id: 'msg_123',
        role: 'assistant',
        type: 'message',
        model: 'claude-3-opus-20240229',
        content: [{type: 'text', text: 'Hello from Opus!'}],
        stop_reason: 'end_turn',
        usage: {input_tokens: 10, output_tokens: 8},
      })
      .mockResolvedValueOnce({
        id: 'msg_456',
        role: 'assistant',
        type: 'message',
        model: 'claude-3-haiku-20240307',
        content: [{type: 'text', text: 'Hello from Haiku!'}],
        stop_reason: 'end_turn',
        usage: {input_tokens: 5, output_tokens: 4},
      });

    // Create instance and make calls
    const anthropic = new patchedAnthropic.Anthropic.Messages();
    await anthropic.create(options1);
    await anthropic.create(options2);

    // Wait for pending operations to complete
    await inMemoryTraceServer.waitForPendingOperations();

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(2);

    // Check first call
    expect(calls[0].summary).toEqual({
      usage: {
        'claude-3-opus-20240229': {
          input_tokens: 10,
          output_tokens: 8,
          requests: 1,
        },
      },
    });

    // Check second call
    expect(calls[1].summary).toEqual({
      usage: {
        'claude-3-haiku-20240307': {
          input_tokens: 5,
          output_tokens: 4,
          requests: 1,
        },
      },
    });
  });
});
