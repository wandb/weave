import {ReadableStream} from 'stream/web';
import {Api as TraceServerApi} from '../generated/traceServerApi';
import {WandbServerApi} from '../wandb/wandbServerApi';
import {WeaveClient} from '../weaveClient';

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
    it('should fetch and return calls', async () => {
      const mockCalls = [
        {id: '1', name: 'call1'},
        {id: '2', name: 'call2'},
      ];
      mockStreamResponse(mockTraceServerApi, mockCalls);

      // Call the method
      const filter = {};
      const includeCosts = true;
      const limit = 500;
      const result = await client.getCalls(filter, includeCosts, limit);

      // Verify the results
      expect(result).toEqual(mockCalls);
      expect(
        mockTraceServerApi.calls.callsQueryStreamCallsStreamQueryPost
      ).toHaveBeenCalledWith({
        project_id: 'test-project',
        filter,
        include_costs: includeCosts,
        limit,
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

      const result = await client.getCalls();

      // Should process both objects, including the one without newline
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
});
