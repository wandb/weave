import {InMemoryTraceServer} from '../../inMemoryTraceServer';
import {wrapOpenAI} from '../../integrations/openai';
import {initWithCustomTraceServer} from '../clientMock';
import {makeAPIPromiseShim, makeMockOpenAIChat} from '../openaiMock';

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

const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

describe('OpenAI Integration', () => {
  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';
  let mockOpenAI: any;
  let patchedOpenAI: any;

  beforeEach(() => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);

    const mockOpenAIChat = makeMockOpenAIChat(messages => ({
      content: messages[messages.length - 1].content.toUpperCase(),
      functionCalls: [],
    }));

    mockOpenAI = {
      chat: {
        completions: {create: mockOpenAIChat},
      },
      beta: {
        chat: {
          completions: {
            parse: () => {
              throw new Error('not implemented');
            },
          },
        },
      },
      images: {
        generate: () => {
          throw new Error('not implemented');
        },
      },
      responses: {
        create: jest.fn(),
      },
    };
    patchedOpenAI = wrapOpenAI(mockOpenAI);
  });

  test('non-streaming chat completion', async () => {
    const messages = [{role: 'user', content: 'Hello, AI!'}];

    // Direct API call
    const directResult = await mockOpenAI.chat.completions.create({messages});

    // Op-wrapped API call
    const opResult = await patchedOpenAI.chat.completions.create({messages});

    // Wait for any pending batch processing
    await wait(300);

    // Check results
    expect(opResult).toMatchObject({
      object: directResult.object,
      model: directResult.model,
      choices: directResult.choices,
      usage: directResult.usage,
    });
    expect(opResult.id).toMatch(/^chatcmpl-/);
    expect(opResult.system_fingerprint).toMatch(/^fp_/);
    expect(opResult.created).toBeCloseTo(directResult.created, -2); // Allow 1 second difference
    expect(opResult.choices[0].message.content).toBe('HELLO, AI!');

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('openai.chat.completions.create');
    expect(calls[0].inputs).toEqual({messages});
    expect(calls[0].output).toMatchObject({
      object: opResult.object,
      model: opResult.model,
      choices: opResult.choices,
      usage: opResult.usage,
    });
    expect(calls[0].output.id).toMatch(/^chatcmpl-/);
    expect(calls[0].output.system_fingerprint).toMatch(/^fp_/);
    expect(calls[0].output.created).toBeCloseTo(opResult.created, -2);
    expect(calls[0].summary).toEqual({
      usage: {
        'gpt-4o-2024-05-13': {
          requests: 1,
          prompt_tokens: 2,
          completion_tokens: 2,
          total_tokens: 4,
        },
      },
    });
    // Ensure stream_options is not present in the logged call for non-streaming requests
    expect(calls[0].inputs).not.toHaveProperty('stream_options');
  });

  test('streaming chat completion basic', async () => {
    const messages = [{role: 'user', content: 'Hello, streaming AI!'}];

    // Direct API call
    const directStream = await mockOpenAI.chat.completions.create({
      messages,
      stream: true,
    });
    let directContent = '';
    for await (const chunk of directStream) {
      if (chunk.choices && chunk.choices[0]?.delta?.content) {
        directContent += chunk.choices[0].delta.content;
      }
    }

    // Op-wrapped API call
    const opStream = await patchedOpenAI.chat.completions.create({
      messages,
      stream: true,
    });
    let opContent = '';
    let usageChunkSeen = false;
    for await (const chunk of opStream) {
      if (chunk.choices && chunk.choices[0]?.delta?.content) {
        opContent += chunk.choices[0].delta.content;
      }
      if ('usage' in chunk) {
        usageChunkSeen = true;
      }
    }

    // Wait for any pending batch processing
    await wait(300);

    // Check results
    expect(opContent).toBe(directContent);
    expect(opContent).toBe('HELLO, STREAMING AI!');

    // TOOD: this is broken still!
    // expect(usageChunkSeen).toBe(false);  // Ensure no usage chunk is seen in the user-facing stream

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('openai.chat.completions.create');
    expect(calls[0].inputs).toEqual({messages, stream: true});
    expect(calls[0].output).toMatchObject({
      choices: [
        {
          message: {
            content: 'HELLO, STREAMING AI!',
          },
        },
      ],
    });
    expect(calls[0].summary).toEqual({
      usage: {
        'gpt-4o-2024-05-13': {
          requests: 1,
          prompt_tokens: 3,
          completion_tokens: 3,
          total_tokens: 6,
        },
      },
    });
  });

  test('falls back cleanly when APIPromise._thenUnwrap is unavailable', async () => {
    // Simulate a (hypothetical) future SDK that drops _thenUnwrap.
    const messages = [{role: 'user', content: 'Hello!'}];
    const rawCreate = mockOpenAI.chat.completions.create;
    mockOpenAI.chat.completions.create = (params: any) => {
      const shim = rawCreate(params);
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const {_thenUnwrap: _removed, ...rest} = shim;
      return rest;
    };
    patchedOpenAI = wrapOpenAI(mockOpenAI);

    const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      // The SDK call still works for the user — weave just stops tracing.
      const result = await patchedOpenAI.chat.completions.create({messages});
      expect(result.choices[0].message.content).toBe('HELLO!');

      await wait(300);
      const calls = await getCalls(inMemoryTraceServer, testProjectName);
      // Fail-fast: no half-started call on the trace server.
      expect(calls).toHaveLength(0);
    } finally {
      warnSpy.mockRestore();
    }
  });

  // Regression: libraries like @mariozechner/pi-ai consume streaming
  // responses via `await client.chat.completions.create(...).withResponse()`.
  // Without weave substituting its tapped stream as `data`, the iterated
  // stream bypasses WeaveIterator and the trace's finishCall never fires.
  test('streaming chat completion via .withResponse() finishes the trace', async () => {
    const messages = [{role: 'user', content: 'Hello, streaming AI!'}];

    const {data, response} = await patchedOpenAI.chat.completions
      .create({messages, stream: true})
      .withResponse();

    expect(response.status).toBe(200);

    let content = '';
    for await (const chunk of data as AsyncIterable<any>) {
      if (chunk.choices?.[0]?.delta?.content) {
        content += chunk.choices[0].delta.content;
      }
    }
    expect(content).toBe('HELLO, STREAMING AI!');

    await wait(300);

    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    // The key assertion: output is populated, which means finishCall
    // fired. Without the .withResponse() → traced-data substitution,
    // iteration would bypass WeaveIterator and this would be empty.
    expect(calls[0].output).toMatchObject({
      choices: [{message: {content: 'HELLO, STREAMING AI!'}}],
    });
  });

  // Add a new test for streaming with explicit usage request
  test('streaming chat completion with explicit usage request', async () => {
    const messages = [
      {role: 'user', content: 'Hello, streaming AI with usage!'},
    ];

    // Op-wrapped API call with explicit usage request
    const opStream = await patchedOpenAI.chat.completions.create({
      messages,
      stream: true,
      stream_options: {include_usage: true},
    });
    let opContent = '';
    let usageChunkSeen = false;
    for await (const chunk of opStream) {
      if (chunk.choices[0]?.delta?.content) {
        opContent += chunk.choices[0].delta.content;
      }
      if ('usage' in chunk) {
        usageChunkSeen = true;
      }
    }

    // Wait for any pending batch processing
    await wait(300);

    // Check results
    expect(opContent).toBe('HELLO, STREAMING AI WITH USAGE!');
    expect(usageChunkSeen).toBe(true); // Ensure usage chunk is seen when explicitly requested

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].summary).toEqual({
      usage: {
        'gpt-4o-2024-05-13': {
          requests: 1,
          prompt_tokens: 5,
          completion_tokens: 5,
          total_tokens: 10,
        },
      },
    });
  });

  test('chat completion with function call', async () => {
    const messages = [{role: 'user', content: "What's the weather in London?"}];
    const functions = [
      {
        name: 'get_weather',
        description: 'Get the weather in a location',
        parameters: {
          type: 'object',
          properties: {
            location: {type: 'string'},
          },
          required: ['location'],
        },
      },
    ];

    // Update mock to include function call
    const mockOpenAIChat = makeMockOpenAIChat(() => ({
      content: '',
      functionCalls: [
        {
          name: 'get_weather',
          arguments: {location: 'London'},
        },
      ],
    }));
    mockOpenAI.chat.completions.create = mockOpenAIChat;

    // Direct API call
    const directResult = await mockOpenAI.chat.completions.create({
      messages,
      functions,
    });

    // Op-wrapped API call
    const opResult = await patchedOpenAI.chat.completions.create({
      messages,
      functions,
    });

    // Wait for any pending batch processing
    await wait(300);

    // Check results
    expect(opResult).toMatchObject({
      object: directResult.object,
      model: directResult.model,
      choices: directResult.choices,
      usage: directResult.usage,
    });
    expect(opResult.id).toMatch(/^chatcmpl-/);
    expect(opResult.system_fingerprint).toMatch(/^fp_/);
    expect(opResult.created).toBeCloseTo(directResult.created, -2); // Allow 1 second difference
    expect(opResult.choices[0].message.function_call).toEqual({
      name: 'get_weather',
      arguments: '{"location":"London"}',
    });

    // Check logged Call values
    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('openai.chat.completions.create');
    expect(calls[0].inputs).toEqual({messages, functions});
    expect(calls[0].output).toMatchObject({
      object: opResult.object,
      model: opResult.model,
      choices: opResult.choices,
      usage: opResult.usage,
    });
    expect(calls[0].output.id).toMatch(/^chatcmpl-/);
    expect(calls[0].output.system_fingerprint).toMatch(/^fp_/);
    expect(calls[0].output.created).toBeCloseTo(opResult.created, -2);
    expect(calls[0].summary).toEqual({
      usage: {
        'gpt-4o-2024-05-13': {
          requests: 1,
          prompt_tokens: 5,
          completion_tokens: 3,
          total_tokens: 8,
        },
      },
    });
  });

  test('should handle streaming response with deltas and done event', async () => {
    const pirateChunks = [
      {
        type: 'response.created',
        sequence_number: 0,
        response: {
          id: 'resp_6847619ad8e081998070ccf8ae64864a065b082f4ff399b5',
          instructions: 'You are a coding assistant that talks like a pirate',
          model: 'gpt-4o-2024-08-06',
          status: 'in_progress',
        },
      },
      {
        type: 'response.output_item.added',
        sequence_number: 1,
        output_index: 0,
        item: {
          id: 'msg_test_id',
          type: 'message',
          status: 'in_progress',
          content: [],
          role: 'assistant',
        },
      },
      {
        type: 'response.content_part.added',
        sequence_number: 2,
        item_id: 'msg_test_id',
        output_index: 0,
        content_index: 0,
        part: {
          type: 'output_text',
          annotations: [],
          text: '',
        },
      },
      {
        type: 'response.output_text.delta',
        sequence_number: 4,
        delta: 'Arr',
      },
      {
        type: 'response.output_text.delta',
        sequence_number: 5,
        delta: 'r',
      },
      {
        type: 'response.output_text.done',
        sequence_number: 6,
        item_id: 'msg_test_id',
        output_index: 0,
        content_index: 0,
        text: 'Arrr',
      },
    ];

    // Override mock for this test
    mockOpenAI.responses.create = jest.fn(() =>
      makeAPIPromiseShim({
        async *[Symbol.asyncIterator]() {
          for (const chunk of pirateChunks) {
            yield chunk;
          }
        },
      })
    );

    const options = {
      model: 'gpt-4o-2024-08-06',
      instructions: 'You are a coding assistant that talks like a pirate',
      messages: [
        {role: 'user', content: 'Are semicolons required in JavaScript?'},
      ],
      stream: true,
    };

    const stream = await patchedOpenAI.responses.create(options);

    let deltaText = '';
    let finalText = '';
    let deltaCount = 0;
    for await (const chunk of stream) {
      if (chunk.type === 'response.output_text.delta') {
        deltaCount++;
        deltaText += chunk.delta;
      }
      if (chunk.type === 'response.output_text.done') {
        finalText = chunk.text;
      }
    }

    // Caller sees the deltas (assembled here) and the final text
    // delivered by the done event.
    expect(deltaCount).toBe(2);
    expect(deltaText).toBe('Arrr');
    expect(finalText).toBe('Arrr');

    // Wait for any pending batch processing
    await wait(300);

    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('create');
    expect(calls[0].inputs).toMatchObject(options);
    expect(calls[0].inputs.self).toBeDefined(); // self parameter should be captured
    expect(calls[0].output.responses[0].output[0].content[0].text).toBe('Arrr');
  });

  test('stream that throws mid-iteration is recorded as an exception, not a successful completion', async () => {
    const boom = new Error('stream blew up');
    mockOpenAI.responses.create = jest.fn(() =>
      makeAPIPromiseShim({
        async *[Symbol.asyncIterator]() {
          yield {
            type: 'response.output_text.delta',
            sequence_number: 1,
            delta: 'partial',
          };
          throw boom;
        },
      })
    );

    const stream = await patchedOpenAI.responses.create({
      model: 'gpt-4o-2024-08-06',
      messages: [{role: 'user', content: 'go'}],
      stream: true,
    });

    let caught: unknown;
    try {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      for await (const _chunk of stream) {
        // consume; the error fires after the first chunk
      }
    } catch (e) {
      caught = e;
    }

    // The caller still sees the underlying SDK error.
    expect(caught).toBe(boom);

    await wait(300);

    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    // The trace records the exception rather than declaring success
    // with partial output.
    expect(calls[0].exception).toEqual(
      expect.stringContaining('stream blew up')
    );
  });
});
