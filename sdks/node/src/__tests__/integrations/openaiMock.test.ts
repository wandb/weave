import {makeMockOpenAIChat} from '../openaiMock';

describe('OpenAI Mock', () => {
  const mockResponse = (messages: any[]) => ({
    content: messages[0].content.toUpperCase(),
    functionCalls: [
      {
        name: 'test_function',
        arguments: {arg: 'value'},
      },
    ],
  });

  test('non-streaming response', async () => {
    const testOpenAIChat = makeMockOpenAIChat(mockResponse);
    const response = await testOpenAIChat({
      messages: [{role: 'user', content: 'Hello, AI!'}],
    });

    expect(response).toEqual({
      id: expect.any(String),
      object: 'chat.completion',
      created: expect.any(Number),
      model: 'gpt-4o-2024-05-13',
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: 'HELLO, AI!',
            function_call: {
              name: 'test_function',
              arguments: '{"arg":"value"}',
            },
            refusal: null,
          },
          logprobs: null,
          finish_reason: 'function_call',
        },
      ],
      usage: {
        prompt_tokens: 2,
        completion_tokens: 4, // 2 for content + 2 for function call
        total_tokens: 6,
      },
      system_fingerprint: expect.any(String),
    });
  });

  test('streaming response without include_usage', async () => {
    const testOpenAIChat = makeMockOpenAIChat(mockResponse);
    const stream = (await testOpenAIChat({
      messages: [{role: 'user', content: 'Hello, AI!'}],
      stream: true,
    })) as AsyncIterable<any>;

    let chunks = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }

    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks[0]).toEqual({
      id: expect.any(String),
      object: 'chat.completion.chunk',
      created: expect.any(Number),
      model: 'gpt-4o-2024-05-13',
      system_fingerprint: expect.any(String),
      choices: [
        {
          index: 0,
          delta: {role: 'assistant', content: '', refusal: null},
          logprobs: null,
          finish_reason: null,
        },
      ],
    });
    expect(chunks[chunks.length - 1]).toEqual({
      id: expect.any(String),
      object: 'chat.completion.chunk',
      created: expect.any(Number),
      model: 'gpt-4o-2024-05-13',
      system_fingerprint: expect.any(String),
      choices: [
        {
          index: 0,
          delta: {},
          logprobs: null,
          finish_reason: 'function_call',
        },
      ],
    });
    expect(chunks.every(chunk => !('usage' in chunk))).toBe(true);
  });

  test('streaming response with include_usage', async () => {
    const testOpenAIChat = makeMockOpenAIChat(mockResponse);
    const stream = (await testOpenAIChat({
      messages: [{role: 'user', content: 'Hello, AI!'}],
      stream: true,
      stream_options: {include_usage: true},
    })) as AsyncIterable<any>;

    let chunks = [];
    for await (const chunk of stream) {
      chunks.push(chunk);
    }

    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks[0]).toEqual({
      id: expect.any(String),
      object: 'chat.completion.chunk',
      created: expect.any(Number),
      model: 'gpt-4o-2024-05-13',
      system_fingerprint: expect.any(String),
      choices: [
        {
          index: 0,
          delta: {role: 'assistant', content: '', refusal: null},
          logprobs: null,
          finish_reason: null,
        },
      ],
      usage: null,
    });
    expect(chunks[chunks.length - 2]).toEqual({
      id: expect.any(String),
      object: 'chat.completion.chunk',
      created: expect.any(Number),
      model: 'gpt-4o-2024-05-13',
      system_fingerprint: expect.any(String),
      choices: [
        {
          index: 0,
          delta: {},
          logprobs: null,
          finish_reason: 'function_call',
        },
      ],
      usage: null,
    });
    expect(chunks[chunks.length - 1]).toEqual({
      id: expect.any(String),
      object: 'chat.completion.chunk',
      created: expect.any(Number),
      model: 'gpt-4o-2024-05-13',
      system_fingerprint: expect.any(String),
      choices: [],
      usage: {
        prompt_tokens: 2,
        completion_tokens: 4,
        total_tokens: 6,
      },
    });
    expect(chunks.slice(0, -1).every(chunk => chunk.usage === null)).toBe(true);
  });
});
