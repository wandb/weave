import {ReadableStream} from 'stream/web';
import {type Api as TraceServerApi} from '../generated/traceServerApi';
import {StringPrompt} from '../prompt';
import * as registryLinkBindings from '../traceServerBindings/linkAssetToRegistry';
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

type MockedTraceServer = jest.Mocked<TraceServerApi<any>> & {
  calls: {callsQueryStreamCallsStreamQueryPost: jest.Mock};
  agents: {
    genaiAgentsQueryAgentsQueryPost: jest.Mock;
    genaiAgentVersionsQueryAgentsAgentVersionsQueryPost: jest.Mock;
    genaiSearchAgentsSearchPost: jest.Mock;
    genaiSpansQueryAgentsSpansQueryPost: jest.Mock;
    genaiSpansStatsAgentsSpansStatsPost: jest.Mock;
    genaiTracesChatAgentsTracesChatPost: jest.Mock;
    genaiConversationChatAgentsConversationsChatPost: jest.Mock;
  };
};

describe('WeaveClient', () => {
  let client: WeaveClient;
  let mockTraceServerApi: MockedTraceServer;

  beforeEach(() => {
    mockTraceServerApi = {
      calls: {
        callsQueryStreamCallsStreamQueryPost: jest.fn(),
      },
      agents: {
        genaiAgentsQueryAgentsQueryPost: jest.fn(),
        genaiAgentVersionsQueryAgentsAgentVersionsQueryPost: jest.fn(),
        genaiSearchAgentsSearchPost: jest.fn(),
        genaiSpansQueryAgentsSpansQueryPost: jest.fn(),
        genaiSpansStatsAgentsSpansStatsPost: jest.fn(),
        genaiTracesChatAgentsTracesChatPost: jest.fn(),
        genaiConversationChatAgentsConversationsChatPost: jest.fn(),
      },
    } as any;
    client = new WeaveClient({
      traceServerApi: mockTraceServerApi,
      projectId: 'test-project',
    });
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

    beforeEach(() => {
      mockTraceServerApi = {
        call: {
          callStartBatchCallUpsertBatchPost: jest.fn().mockResolvedValue({}),
        },
      } as any;
      client = new WeaveClient({
        traceServerApi: mockTraceServerApi,
        projectId: 'test-project',
      });
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

  describe('getAgents', () => {
    it('gets agents from the server', async () => {
      const agents = [{agent_name: 'Assistant', total_input_tokens: 42}];
      mockTraceServerApi.agents.genaiAgentsQueryAgentsQueryPost.mockResolvedValue(
        {data: {agents, total_count: 1}} as any
      );

      const result = await client.getAgents({
        limit: 50,
        offset: 10,
        sortBy: [{field: 'last_seen', direction: 'desc'}],
      });

      expect(
        mockTraceServerApi.agents.genaiAgentsQueryAgentsQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        sort_by: [{field: 'last_seen', direction: 'desc'}],
        limit: 50,
        offset: 10,
      });

      expect(result).toEqual({data: {agents, total_count: 1}});
    });

    it('gets agent by name', async () => {
      const agents = [{agent_name: 'Assistant', total_input_tokens: 42}];
      mockTraceServerApi.agents.genaiAgentsQueryAgentsQueryPost.mockResolvedValue(
        {data: {agents, total_count: 1}} as any
      );

      const result = await client.getAgents({
        agentName: 'my-cool-agent',
      });

      expect(
        mockTraceServerApi.agents.genaiAgentsQueryAgentsQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        filters: {
          agent_name: 'my-cool-agent',
        },
      });

      expect(result).toEqual({data: {agents, total_count: 1}});
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiAgentsQueryAgentsQueryPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(client.getAgents()).rejects.toThrow('boom');
    });
  });

  describe('getAgentVersions', () => {
    it('gets agent versions from the server', async () => {
      const versions = [
        {agent_version: 'v1', total_input_tokens: 42},
        {agent_version: 'v2', total_input_tokens: 99},
      ];
      mockTraceServerApi.agents.genaiAgentVersionsQueryAgentsAgentVersionsQueryPost.mockResolvedValue(
        {data: {versions, total_count: 2}} as any
      );

      const result = await client.getAgentVersions({
        agentName: 'Assistant',
        limit: 50,
        offset: 10,
        sortBy: [{field: 'last_seen', direction: 'desc'}],
      });

      expect(
        mockTraceServerApi.agents
          .genaiAgentVersionsQueryAgentsAgentVersionsQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        agent_name: 'Assistant',
        sort_by: [{field: 'last_seen', direction: 'desc'}],
        limit: 50,
        offset: 10,
      });

      expect(result).toEqual({data: {versions, total_count: 2}});
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiAgentVersionsQueryAgentsAgentVersionsQueryPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(
        client.getAgentVersions({agentName: 'Assistant'})
      ).rejects.toThrow('boom');
    });
  });

  describe('getAgentSpans', () => {
    it('gets agent spans from the server filtered by agent name', async () => {
      const spans = [
        {span_id: 's1', span_name: 'invoke_agent', input_tokens: 42},
        {span_id: 's2', span_name: 'chat_completion', input_tokens: 99},
      ];
      mockTraceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost.mockResolvedValue(
        {data: {spans, total_count: 2}} as any
      );

      const result = await client.getAgentSpans({
        agentName: 'Assistant',
        limit: 50,
        offset: 10,
        sortBy: [{field: 'started_at', direction: 'desc'}],
      });

      expect(
        mockTraceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        sort_by: [{field: 'started_at', direction: 'desc'}],
        limit: 50,
        offset: 10,
        query: {
          $expr: {
            $eq: [{$getField: 'agent_name'}, {$literal: 'Assistant'}],
          },
        },
      });

      expect(result).toEqual({data: {spans, total_count: 2}});
    });

    it('omits the query when no agent name is provided', async () => {
      mockTraceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost.mockResolvedValue(
        {data: {spans: [], total_count: 0}} as any
      );

      await client.getAgentSpans({limit: 5});

      expect(
        mockTraceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        sort_by: undefined,
        limit: 5,
        offset: undefined,
      });
    });

    it('defaults spans to an empty array when the server omits them', async () => {
      mockTraceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost.mockResolvedValue(
        {data: {total_count: 0}} as any
      );

      const result = await client.getAgentSpans({});

      expect(result.data.spans).toEqual([]);
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(client.getAgentSpans({})).rejects.toThrow('boom');
    });
  });

  describe('getAgentSpanStats', () => {
    it('gets agent span stats from the server', async () => {
      const stats = {
        start: '2026-06-10T00:00:00Z',
        end: '2026-06-23T00:00:00Z',
        granularity: 86400,
        timezone: 'UTC',
        bucket_type: 'time',
        columns: [
          {name: 'started_at_bucket', role: 'time', value_type: 'datetime'},
          {
            name: 'total_input_tokens',
            role: 'metric',
            value_type: 'number',
            metric: 'total_input_tokens',
            aggregation: 'sum',
          },
        ],
        rows: [{started_at_bucket: '2026-06-10T00:00:00Z', total_input_tokens: 450}],
      };
      mockTraceServerApi.agents.genaiSpansStatsAgentsSpansStatsPost.mockResolvedValue(
        {data: stats} as any
      );

      const metrics = [
        {
          alias: 'total_input_tokens',
          value_type: 'number' as const,
          aggregations: ['sum' as const],
          value: {source: 'field' as const, key: 'input_tokens'},
        },
      ];
      const groupBy = [{key: 'agent_name'}];
      const query = {
        $expr: {
          $eq: [{$getField: 'provider_name'}, {$literal: 'openai'}],
        },
      };

      const result = await client.getAgentSpanStats({
        start: '2026-06-10T00:00:00Z',
        end: '2026-06-23T00:00:00Z',
        metrics,
        groupBy,
        query,
        granularity: 86400,
        timezone: 'America/Los_Angeles',
      });

      expect(
        mockTraceServerApi.agents.genaiSpansStatsAgentsSpansStatsPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        start: '2026-06-10T00:00:00Z',
        end: '2026-06-23T00:00:00Z',
        metrics,
        group_by: groupBy,
        query,
        granularity: 86400,
        timezone: 'America/Los_Angeles',
      });

      expect(result).toEqual({data: stats});
    });

    it('fetches without optional fields', async () => {
      mockTraceServerApi.agents.genaiSpansStatsAgentsSpansStatsPost.mockResolvedValue(
        {data: {start: '', end: '', timezone: 'UTC'}} as any
      );

      await client.getAgentSpanStats({start: '2026-06-10T00:00:00Z'});

      expect(
        mockTraceServerApi.agents.genaiSpansStatsAgentsSpansStatsPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        start: '2026-06-10T00:00:00Z',
      });
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiSpansStatsAgentsSpansStatsPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(
        client.getAgentSpanStats({start: '2026-06-10T00:00:00Z'})
      ).rejects.toThrow('boom');
    });
  });

  describe('getAgentTurn', () => {
    it('gets turn data for a given trace id', async () => {
      const chat = {
        trace_id: 'trace-1',
        root_span_name: 'my-op',
        provider: 'openai',
        total_duration_ms: 1234,
        messages: [],
        feedback: null,
      };
      mockTraceServerApi.agents.genaiTracesChatAgentsTracesChatPost.mockResolvedValue(
        {data: chat} as any
      );

      const result = await client.getAgentTurn({
        traceId: 'trace-1',
        includeFeedback: true,
      });

      expect(
        mockTraceServerApi.agents.genaiTracesChatAgentsTracesChatPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        trace_id: 'trace-1',
        include_feedback: true,
      });

      expect(result).toEqual({data: chat});
    });

    it('passes undefined includeFeedback when omitted', async () => {
      mockTraceServerApi.agents.genaiTracesChatAgentsTracesChatPost.mockResolvedValue(
        {data: {trace_id: 'trace-1'}} as any
      );

      await client.getAgentTurn({traceId: 'trace-1'});

      expect(
        mockTraceServerApi.agents.genaiTracesChatAgentsTracesChatPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        trace_id: 'trace-1',
        include_feedback: undefined,
      });
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiTracesChatAgentsTracesChatPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(client.getAgentTurn({traceId: 'trace-1'})).rejects.toThrow(
        'boom'
      );
    });
  });

  describe('getAgentTurns', () => {
    it('gets turn data for the given conversation id', async () => {
      const chat = {
        conversation_id: 'conv-1',
        turns: [{trace_id: 'trace-1'}],
        total_turns: 1,
        has_more: false,
        limit: 50,
        offset: 0,
        feedback: null,
      };
      mockTraceServerApi.agents.genaiConversationChatAgentsConversationsChatPost.mockResolvedValue(
        {data: chat} as any
      );

      const result = await client.getAgentTurns({
        conversationId: 'conv-1',
        limit: 25,
        offset: 5,
        includeFeedback: true,
      });

      expect(
        mockTraceServerApi.agents
          .genaiConversationChatAgentsConversationsChatPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        conversation_id: 'conv-1',
        limit: 25,
        offset: 5,
        include_feedback: true,
      });

      expect(result).toEqual({data: chat});
    });

    it('passes undefined limit/offset/includeFeedback when omitted', async () => {
      mockTraceServerApi.agents.genaiConversationChatAgentsConversationsChatPost.mockResolvedValue(
        {data: {conversation_id: 'conv-1'}} as any
      );

      await client.getAgentTurns({conversationId: 'conv-1'});

      expect(
        mockTraceServerApi.agents
          .genaiConversationChatAgentsConversationsChatPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        conversation_id: 'conv-1',
        limit: undefined,
        offset: undefined,
        include_feedback: undefined,
      });
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiConversationChatAgentsConversationsChatPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(
        client.getAgentTurns({conversationId: 'conv-1'})
      ).rejects.toThrow('boom');
    });
  });

  describe('searchAgents', () => {
    it('searches agent conversation messages', async () => {
      const results = [
        {
          conversation_id: 'conv-1',
          conversation_name: '',
          agent_name: 'Assistant',
          matched_messages: [
            {
              span_id: 'span-1',
              trace_id: 'trace-1',
              role: 'user',
              content_preview: 'When was the last time Liverpool won?',
              content_digest: 'digest-1',
              started_at: '2026-06-16T22:10:34.631000',
            },
          ],
          last_activity: '2026-06-16T22:10:34.631000',
        },
      ];
      mockTraceServerApi.agents.genaiSearchAgentsSearchPost.mockResolvedValue({
        data: {results, total_conversations: 1},
      } as any);

      const result = await client.searchAgents({
        query: 'Liverpool',
        agentName: 'Assistant',
        conversationId: 'conv-1',
        traceId: 'trace-1',
        limit: 25,
        offset: 5,
      });

      expect(
        mockTraceServerApi.agents.genaiSearchAgentsSearchPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        query: 'Liverpool',
        agent_name: 'Assistant',
        conversation_id: 'conv-1',
        trace_id: 'trace-1',
        limit: 25,
        offset: 5,
      });

      expect(result).toEqual({data: {results, total_conversations: 1}});
    });

    it('searches without optional fields', async () => {
      mockTraceServerApi.agents.genaiSearchAgentsSearchPost.mockResolvedValue({
        data: {results: [], total_conversations: 0},
      } as any);

      await client.searchAgents({query: 'Liverpool'});

      expect(
        mockTraceServerApi.agents.genaiSearchAgentsSearchPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        query: 'Liverpool',
      });
    });

    it('propagates errors from the underlying API', async () => {
      mockTraceServerApi.agents.genaiSearchAgentsSearchPost.mockRejectedValue(
        new Error('boom')
      );

      await expect(client.searchAgents({query: 'Liverpool'})).rejects.toThrow(
        'boom'
      );
    });
  });

  describe('linkPromptToRegistry', () => {
    let client: WeaveClient;
    let mockTraceServerApi: jest.Mocked<TraceServerApi<any>>;
    let mockTransport: jest.SpyInstance;

    beforeEach(() => {
      mockTraceServerApi = {
        request: jest.fn(),
      } as any;
      client = new WeaveClient({
        traceServerApi: mockTraceServerApi,
        projectId: 'current-entity/current-project',
      });
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
      const unscopedClient = new WeaveClient({
        traceServerApi: mockTraceServerApi,
        projectId: 'project-only',
      });
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
