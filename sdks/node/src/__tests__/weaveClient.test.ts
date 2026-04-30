import {ReadableStream} from 'stream/web';
import {Api as TraceServerApi} from '../generated/traceServerApi';
import {StringPrompt} from '../prompt';
import * as registryLinkBindings from '../traceServerBindings/linkAssetToRegistry';
import {WandbServerApi} from '../wandb/wandbServerApi';
import {WeaveClient} from '../weaveClient';
import {ObjectRef} from '../weaveObject';

// Mock the TraceServerApi and WandbServerApi
jest.mock('../generated/traceServerApi');
jest.mock('../wandb/wandbServerApi');

function createStreamFromCalls(calls: any[] = []) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      calls.forEach(call => {
        controller.enqueue(encoder.encode(JSON.stringify(call) + '\n'));
      });
      controller.close();
    },
  });
  return stream;
}
function mockStreamResponse(
  api: jest.Mocked<TraceServerApi<any>>,
  calls: any[]
) {
  const stream = createStreamFromCalls(calls);
  (
    api.calls.callsQueryStreamCallsStreamQueryPost as jest.Mock
  ).mockResolvedValue({
    body: stream,
  } as any);
}

describe('WeaveClient', () => {
  let client: WeaveClient;
  let mockTraceServerApi: jest.Mocked<TraceServerApi<any>>;
  let mockWandbServerApi: jest.Mocked<WandbServerApi>;

  beforeEach(() => {
    mockTraceServerApi = {
      calls: {
        callsQueryStreamCallsStreamQueryPost: jest.fn(),
      },
    } as any;
    mockWandbServerApi = {} as any;
    client = new WeaveClient(
      mockTraceServerApi,
      mockWandbServerApi,
      'test-project'
    );
  });

  describe('getCalls', () => {
    it('should fetch and return calls with the legacy signature', async () => {
      const mockCalls = [
        {id: '1', name: 'call1'},
        {id: '2', name: 'call2'},
      ];
      mockStreamResponse(mockTraceServerApi, mockCalls);

      const filter = {op_names: ['legacy-op']};
      const includeCosts = true;
      const limit = 500;
      const result = await client.getCalls(filter, includeCosts, limit);

      expect(result).toEqual(mockCalls);
      expect(
        mockTraceServerApi.calls.callsQueryStreamCallsStreamQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        filter,
        query: undefined,
        include_costs: includeCosts,
        include_feedback: undefined,
        limit,
        offset: undefined,
        sort_by: undefined,
        columns: undefined,
        expand_columns: undefined,
      });

      (
        mockTraceServerApi.calls
          .callsQueryStreamCallsStreamQueryPost as jest.Mock
      ).mockClear();
      mockStreamResponse(mockTraceServerApi, mockCalls);

      // Test that the parameterless call signature is supported.
      const defaultResult = await client.getCalls();

      expect(defaultResult).toEqual(mockCalls);
    });

    it('should fetch and return calls with the options signature', async () => {
      const mockCalls = [
        {id: '1', name: 'call1'},
        {id: '2', name: 'call2'},
      ];
      mockStreamResponse(mockTraceServerApi, mockCalls);

      const result = await client.getCalls({
        filter: {},
        includeCosts: true,
        limit: 500,
      });

      expect(result).toEqual(mockCalls);
      expect(
        mockTraceServerApi.calls.callsQueryStreamCallsStreamQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        filter: {},
        query: undefined,
        include_costs: true,
        include_feedback: undefined,
        limit: 500,
        offset: undefined,
        sort_by: undefined,
        columns: undefined,
        expand_columns: undefined,
      });
    });

    it('should support the options form with query parameters', async () => {
      const mockCalls = [{id: '1', name: 'call1'}];
      const query = {
        $expr: {
          $eq: [{$getField: 'display_name'}, {$literal: 'target-call'}],
        },
      };
      const sortBy = [{field: 'started_at', direction: 'desc' as const}];
      mockStreamResponse(mockTraceServerApi, mockCalls);

      const result = await client.getCalls({
        filter: {op_names: ['demo-op']},
        query,
        includeCosts: true,
        includeFeedback: true,
        limit: 25,
        offset: 10,
        sortBy,
        columns: ['id', 'display_name'],
        expandColumns: ['inputs.prompt'],
      });

      expect(result).toEqual(mockCalls);
      expect(
        mockTraceServerApi.calls.callsQueryStreamCallsStreamQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        filter: {op_names: ['demo-op']},
        query,
        include_costs: true,
        include_feedback: true,
        limit: 25,
        offset: 10,
        sort_by: sortBy,
        columns: ['id', 'display_name'],
        expand_columns: ['inputs.prompt'],
      });
    });

    it('should handle remaining buffer data after stream ends', async () => {
      const encoder = new TextEncoder();
      const stream = new ReadableStream({
        start(controller) {
          // Send data without newline at the end
          controller.enqueue(encoder.encode('{"id": "1"}\n{"id": "2"}'));
          controller.close();
        },
      });

      (
        mockTraceServerApi.calls
          .callsQueryStreamCallsStreamQueryPost as jest.Mock
      ).mockResolvedValue({
        body: stream,
      } as any);

      const result = await client.getCalls({});

      expect(result).toEqual([{id: '1'}, {id: '2'}]);
    });
  });

  describe('Batch Processing', () => {
    let client: WeaveClient;
    let mockTraceServerApi: jest.Mocked<TraceServerApi<any>>;
    let mockWandbServerApi: jest.Mocked<WandbServerApi>;

    beforeEach(() => {
      mockTraceServerApi = {
        call: {
          callStartBatchCallUpsertBatchPost: jest.fn().mockResolvedValue({}),
        },
      } as any;
      mockWandbServerApi = {} as any;
      client = new WeaveClient(
        mockTraceServerApi,
        mockWandbServerApi,
        'test-project'
      );
      // Speed up tests by reducing batch interval
      (client as any).BATCH_INTERVAL = 10;
    });

    it('should handle oversized batch items', async () => {
      const bigPayloadSize = 11 * 1024 * 1024;
      const smallData = {mode: 'start', data: {id: '2', payload: 'small'}};
      const bigData = {
        mode: 'start',
        data: {id: '1', payload: 'x'.repeat(bigPayloadSize)},
      };
      (client as any).callQueue.push(smallData, bigData);

      await (client as any).processBatch();

      expect(
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost
      ).toHaveBeenCalledWith({
        batch: [{mode: 'start', req: smallData.data}],
      });

      expect((client as any).callQueue).toContain(bigData);
    });

    it('should batch multiple calls together', async () => {
      // Add test calls to queue
      (client as any).callQueue.push(
        {mode: 'start', data: {id: '1'}},
        {mode: 'start', data: {id: '2'}}
      );

      await (client as any).processBatch();

      expect(
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost
      ).toHaveBeenCalledWith({
        batch: [
          {mode: 'start', req: {id: '1'}},
          {mode: 'start', req: {id: '2'}},
        ],
      });
      expect((client as any).callQueue.length).toBe(0);

      (client as any).callQueue.push(
        {mode: 'start', data: {id: '3'}},
        {mode: 'start', data: {id: '4'}},
        {mode: 'start', data: {id: '5'}}
      );

      await (client as any).processBatch();

      expect(
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost
      ).toHaveBeenCalledWith({
        batch: [
          {mode: 'start', req: {id: '3'}},
          {mode: 'start', req: {id: '4'}},
          {mode: 'start', req: {id: '5'}},
        ],
      });
      expect((client as any).callQueue.length).toBe(0);

      expect(
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost
      ).toHaveBeenCalledTimes(2);
    });

    it('should handle API errors gracefully', async () => {
      const mockConsoleError = jest
        .spyOn(console, 'error')
        .mockImplementation();

      // Add multiple items to queue
      const items = [
        {mode: 'start', data: {id: '1'}},
        {mode: 'start', data: {id: '2'}},
      ];
      (client as any).callQueue.push(...items);

      // First API call fails
      (
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost as jest.Mock
      ).mockRejectedValueOnce(new Error('API Error'));

      await (client as any).processBatch();

      // Should log error but continue processing, with failed items back in queue
      expect(mockConsoleError).toHaveBeenCalledWith(
        'Error processing batch:',
        expect.any(Error)
      );
      expect((client as any).callQueue).toEqual(items);

      // Second API call succeeds
      (
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost as jest.Mock
      ).mockResolvedValueOnce({});

      await (client as any).processBatch();

      // Verify items were processed in original order
      expect(
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost
      ).toHaveBeenCalledWith({
        batch: [
          {mode: 'start', req: {id: '1'}},
          {mode: 'start', req: {id: '2'}},
        ],
      });
      expect((client as any).callQueue.length).toBe(0);

      mockConsoleError.mockRestore();
    });

    it('should prevent concurrent batch processing', async () => {
      (client as any).isBatchProcessing = true;
      (client as any).scheduleBatchProcessing();
      expect((client as any).batchProcessTimeout).toBeNull();
    });

    it('should wait for all pending batches', async () => {
      // Simulate slow API
      (
        mockTraceServerApi.call.callStartBatchCallUpsertBatchPost as jest.Mock
      ).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 50))
      );

      (client as any).callQueue.push(
        {mode: 'start', data: {id: '1'}},
        {mode: 'start', data: {id: '2'}}
      );

      (client as any).scheduleBatchProcessing();
      await client.waitForBatchProcessing();

      expect((client as any).batchProcessingPromises.size).toBe(0);
      expect((client as any).callQueue.length).toBe(0);
    });
  });

  describe('getCall', () => {
    it('should fetch a single call by ID', async () => {
      const mockCall = {id: 'test-id', name: 'test-call'};
      mockStreamResponse(mockTraceServerApi, [mockCall]);

      const result = await client.getCall('test-id');
      expect(result).toEqual(mockCall);
    });

    it('should throw error when call is not found', async () => {
      mockStreamResponse(mockTraceServerApi, []);
      expect(client.getCall('non-existent-id')).rejects.toThrow(
        'Call not found: non-existent-id'
      );
    });
  });

  describe('linkPromptToRegistry', () => {
    let client: WeaveClient;
    let mockTraceServerApi: jest.Mocked<TraceServerApi<any>>;
    let mockWandbServerApi: jest.Mocked<WandbServerApi>;
    let mockTransport: jest.SpyInstance;

    beforeEach(() => {
      mockTraceServerApi = {
        request: jest.fn(),
      } as any;
      mockWandbServerApi = {} as any;
      client = new WeaveClient(
        mockTraceServerApi,
        mockWandbServerApi,
        'current-entity/current-project'
      );
      mockTransport = jest
        .spyOn(registryLinkBindings, 'linkAssetToRegistry')
        .mockResolvedValue({version_index: 0});
    });

    afterEach(() => {
      jest.restoreAllMocks();
    });

    it('resolves a published prompt object and uses the current client entity', async () => {
      const prompt = new StringPrompt({content: 'Hello {name}'});
      prompt.__savedRef = Promise.resolve(
        new ObjectRef('source-entity/source-project', 'my-prompt', 'v1')
      );

      const result = await client.linkPromptToRegistry(prompt, {
        targetPath: 'wandb-registry-prompts/my-prompt-collection',
      });

      expect(result).toEqual({version_index: 0});
      expect(mockTransport).toHaveBeenCalledWith(mockTraceServerApi, {
        ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
        target: {
          entity_name: 'current-entity',
          project_name: 'wandb-registry-prompts',
          portfolio_name: 'my-prompt-collection',
        },
        aliases: [],
      });
    });

    it('accepts ObjectRef input and normalizes aliases', async () => {
      const promptRef = new ObjectRef(
        'source-entity/source-project',
        'my-prompt',
        'v1'
      );

      await client.linkPromptToRegistry(promptRef, {
        targetPath: 'wandb-registry-prompts/my-prompt-collection',
        aliases: ['prod', 'latest'],
      });

      expect(mockTransport).toHaveBeenCalledWith(mockTraceServerApi, {
        ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
        target: {
          entity_name: 'current-entity',
          project_name: 'wandb-registry-prompts',
          portfolio_name: 'my-prompt-collection',
        },
        aliases: ['prod', 'latest'],
      });
    });

    it('accepts URI string input directly', async () => {
      await client.linkPromptToRegistry(
        'weave:///source-entity/source-project/object/my-prompt:v1',
        {
          targetPath: 'wandb-registry-prompts/my-prompt-collection',
        }
      );

      expect(mockTransport).toHaveBeenCalledWith(
        mockTraceServerApi,
        expect.objectContaining({
          ref: 'weave:///source-entity/source-project/object/my-prompt:v1',
        })
      );
    });

    it('throws for unpublished prompt objects', async () => {
      const prompt = new StringPrompt({content: 'Hello {name}'});

      await expect(
        client.linkPromptToRegistry(prompt, {
          targetPath: 'wandb-registry-prompts/my-prompt-collection',
        })
      ).rejects.toThrow('linkPromptToRegistry requires a published prompt');
    });

    it('rejects invalid target paths', async () => {
      const promptRef = new ObjectRef(
        'source-entity/source-project',
        'my-prompt',
        'v1'
      );

      await expect(
        client.linkPromptToRegistry(promptRef, {
          targetPath: 'prompts/my-prompt-collection',
        })
      ).rejects.toThrow(
        "targetPath must match '<registry_project>/<portfolio_name>' where registry_project starts with 'wandb-registry-'"
      );
    });

    it('rejects projectId without entity scope', async () => {
      const unscopedClient = new WeaveClient(
        mockTraceServerApi,
        mockWandbServerApi,
        'project-only'
      );
      const promptRef = new ObjectRef(
        'source-entity/source-project',
        'my-prompt',
        'v1'
      );

      await expect(
        unscopedClient.linkPromptToRegistry(promptRef, {
          targetPath: 'wandb-registry-prompts/my-prompt-collection',
        })
      ).rejects.toThrow(
        "linkPromptToRegistry requires client.projectId in '<entity>/<project>' format"
      );
    });
  });
});
