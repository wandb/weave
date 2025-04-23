import {Api as TraceServerApi} from '../../generated/traceServerApi';
import {
  makeOpenAIImagesGenerateOp,
  openAIStreamReducer,
  wrapOpenAI,
} from '../../integrations/openai';
import {isWeaveImage} from '../../media';
import {WandbServerApi} from '../../wandb/wandbServerApi';
import {WeaveClient} from '../../weaveClient';

// Mock WeaveClient dependencies
jest.mock('../../generated/traceServerApi');
jest.mock('../../wandb/wandbServerApi');

describe('OpenAI Integration', () => {
  let mockOpenAI: any;
  let wrappedOpenAI: any;
  let mockTraceServerApi: jest.Mocked<TraceServerApi<any>>;
  let mockWandbServerApi: jest.Mocked<WandbServerApi>;
  let weaveClient: WeaveClient;

  beforeEach(() => {
    // Setup mock OpenAI client
    mockOpenAI = {
      chat: {
        completions: {
          create: jest.fn(),
        },
      },
      images: {
        generate: jest.fn(),
      },
      beta: {
        chat: {
          completions: {
            parse: jest.fn(),
          },
        },
      },
    };

    // Setup WeaveClient
    mockTraceServerApi = {
      obj: {
        objCreateObjCreatePost: jest.fn().mockResolvedValue({
          data: {digest: 'test-digest'},
        }),
      },
      call: {
        callStartBatchCallUpsertBatchPost: jest.fn(),
      },
    } as any;
    mockWandbServerApi = {} as any;
    weaveClient = new WeaveClient(
      mockTraceServerApi,
      mockWandbServerApi,
      'test-project'
    );

    wrappedOpenAI = wrapOpenAI(mockOpenAI);
  });

  describe('openAIStreamReducer', () => {
    it('should correctly reduce stream chunks for basic chat completion', () => {
      const state = openAIStreamReducer.initialStateFn();

      const chunks = [
        {
          id: 'test-id',
          object: 'chat.completion.chunk',
          created: 1234567890,
          model: 'gpt-4',
          choices: [
            {
              index: 0,
              delta: {
                role: 'assistant',
                content: 'Hello',
              },
            },
          ],
        },
        {
          choices: [
            {
              index: 0,
              delta: {
                content: ' world!',
              },
              finish_reason: 'stop',
            },
          ],
          usage: {
            prompt_tokens: 10,
            completion_tokens: 20,
            total_tokens: 30,
          },
        },
      ];

      let finalState = state;
      chunks.forEach(chunk => {
        finalState = openAIStreamReducer.reduceFn(finalState, chunk);
      });

      expect(finalState).toEqual({
        id: 'test-id',
        object: 'chat.completion.chunk',
        created: 1234567890,
        model: 'gpt-4',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: 'Hello world!',
              function_call: null,
            },
            finish_reason: 'stop',
          },
        ],
        usage: {
          prompt_tokens: 10,
          completion_tokens: 20,
          total_tokens: 30,
        },
      });
    });

    it('should handle function calls in stream chunks', () => {
      const state = openAIStreamReducer.initialStateFn();

      const chunks = [
        {
          id: 'func-call-id',
          choices: [
            {
              delta: {
                role: 'assistant',
                function_call: {
                  name: 'test_function',
                },
              },
            },
          ],
        },
        {
          choices: [
            {
              delta: {
                function_call: {
                  arguments: '{"arg1":',
                },
              },
            },
          ],
        },
        {
          choices: [
            {
              delta: {
                function_call: {
                  arguments: '"value1"}',
                },
              },
              finish_reason: 'function_call',
            },
          ],
        },
      ];

      let finalState = state;
      chunks.forEach(chunk => {
        finalState = openAIStreamReducer.reduceFn(finalState, chunk);
      });

      expect(finalState.choices[0].message.function_call).toEqual({
        name: 'test_function',
        arguments: '{"arg1":"value1"}',
      });
      expect(finalState.choices[0].finish_reason).toBe('function_call');
    });
  });

  describe('wrapOpenAI', () => {
    it('should wrap transparently', async () => {
      const mockCreate = jest.fn(async params => ({
        id: 'test-id',
        choices: [{message: {content: 'Hello'}}],
      }));

      // Test both wrapped and unwrapped versions
      mockOpenAI.chat.completions.create = mockCreate;
      const unwrappedResult = await mockOpenAI.chat.completions.create({
        model: 'gpt-4',
        messages: [{role: 'user', content: 'Hi'}],
      });

      const wrappedResult = await wrappedOpenAI.chat.completions.create({
        model: 'gpt-4',
        messages: [{role: 'user', content: 'Hi'}],
      });

      // Verify wrapped matches unwrapped
      expect(wrappedResult).toEqual(unwrappedResult);
    });
  });
});

describe('makeOpenAIImagesGenerateOp', () => {
  it('converts b64_json images to WeaveImage objects and preserves other items', async () => {
    const mockGenerate = jest.fn().mockResolvedValue({
      data: [
        {
          url: 'https://example.com/image.png',
        },
        {
          b64_json:
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
        },
      ],
    });

    const wrappedGenerate = makeOpenAIImagesGenerateOp(mockGenerate);
    const result = await wrappedGenerate({prompt: 'draw a picture'});

    // Verify the result structure
    expect(result.data).toHaveLength(2);

    // First item should remain unchanged
    expect(result.data[0]).toEqual({url: 'https://example.com/image.png'});

    // Second item should be converted to WeaveImage
    expect(isWeaveImage(result.data[1])).toBe(true);
    expect(result.data[1].imageType).toBe('png');
    expect(Buffer.isBuffer(result.data[1].data)).toBe(true);

    // Verify the original function was called with correct args
    expect(mockGenerate).toHaveBeenCalledWith({prompt: 'draw a picture'});
  });
});
