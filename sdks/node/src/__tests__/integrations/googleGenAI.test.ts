import {InMemoryTraceServer} from '../../inMemoryTraceServer';
import {commonPatchGoogleGenAI} from '../../integrations/googleGenAI';
import {initWithCustomTraceServer} from '../clientMock';

async function getCalls(traceServer: InMemoryTraceServer, projectId: string) {
  return traceServer.calls
    .callsStreamQueryPost({
      project_id: projectId,
      limit: 100,
    })
    .then(result => result.calls);
}

function createMockGoogleGenAI() {
  const mockGenerateContent = jest
    .fn()
    .mockImplementation(async (params: {model: string}) => {
      return {
        modelVersion: params.model,
        usageMetadata: {
          promptTokenCount: 12,
          candidatesTokenCount: 7,
          totalTokenCount: 19,
          thoughtsTokenCount: 3,
        },
        text: 'Hello from Gemini',
      };
    });

  const mockGenerateContentStream = jest
    .fn()
    .mockImplementation(async (_params: {model: string}) => {
      async function* stream() {
        yield {
          modelVersion: 'gemini-2.5-flash',
          text: 'Hello',
        };
        yield {
          text: ' world',
        };
        yield {
          usageMetadata: {
            promptTokenCount: 9,
            candidatesTokenCount: 6,
            totalTokenCount: 15,
          },
        };
      }
      return stream();
    });

  class MockGoogleGenAI {
    public models: {
      generateContent: any;
      generateContentStream: any;
    };
    public chats: {
      modelsModule: any;
    };

    constructor() {
      this.models = {
        generateContent: mockGenerateContent,
        generateContentStream: mockGenerateContentStream,
      };
      this.chats = {
        modelsModule: this.models,
      };
    }
  }

  return {
    mockModule: {GoogleGenAI: MockGoogleGenAI},
    mockGenerateContent,
    mockGenerateContentStream,
  };
}

describe('Google GenAI Integration', () => {
  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(() => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('tracks Gemini token usage for generateContent', async () => {
    const {mockModule, mockGenerateContent} = createMockGoogleGenAI();
    const patchedGoogleGenAI = commonPatchGoogleGenAI(mockModule);
    const client = new patchedGoogleGenAI.GoogleGenAI();

    const response = await client.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: 'Hello Gemini',
    });

    expect(response).toMatchObject({
      modelVersion: 'gemini-2.5-flash',
      text: 'Hello from Gemini',
    });
    expect(mockGenerateContent).toHaveBeenCalledTimes(1);
    expect(client.chats.modelsModule).toBe(client.models);

    await inMemoryTraceServer.waitForPendingOperations();

    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('google.genai.models.generateContent');
    expect(calls[0].inputs).toEqual({
      model: 'gemini-2.5-flash',
      contents: 'Hello Gemini',
    });
    expect(calls[0].summary).toEqual({
      usage: {
        'gemini-2.5-flash': {
          requests: 1,
          prompt_tokens: 12,
          completion_tokens: 7,
          total_tokens: 19,
          thoughts_tokens: 3,
        },
      },
    });
  });

  test('tracks Gemini token usage for generateContentStream', async () => {
    const {mockModule, mockGenerateContentStream} = createMockGoogleGenAI();
    const patchedGoogleGenAI = commonPatchGoogleGenAI(mockModule);
    const client = new patchedGoogleGenAI.GoogleGenAI();

    const stream = await client.models.generateContentStream({
      model: 'gemini-2.5-flash',
      contents: 'Hello Gemini stream',
    });

    let chunkCount = 0;
    for await (const _chunk of stream) {
      chunkCount += 1;
    }
    expect(chunkCount).toBe(3);
    expect(mockGenerateContentStream).toHaveBeenCalledTimes(1);

    await inMemoryTraceServer.waitForPendingOperations();

    const calls = await getCalls(inMemoryTraceServer, testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain(
      'google.genai.models.generateContentStream'
    );
    expect(calls[0].inputs).toEqual({
      model: 'gemini-2.5-flash',
      contents: 'Hello Gemini stream',
    });
    expect(calls[0].summary).toEqual({
      usage: {
        'gemini-2.5-flash': {
          requests: 1,
          prompt_tokens: 9,
          completion_tokens: 6,
          total_tokens: 15,
        },
      },
    });
  });
});
