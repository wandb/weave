import {InMemoryTraceServer} from '../inMemoryTraceServer';
import {makeOpenAIChatCompletionsOp} from '../integrations/openai';
import {op} from '../op';
import {initWithCustomTraceServer} from './clientMock';
import {makeMockOpenAIChat} from './openaiMock';

// Helper function to get calls
async function getCalls(
  traceServer: InMemoryTraceServer,
  projectId: string,
  limit?: number,
  filters?: any
) {
  return traceServer.calls
    .callsStreamQueryPost({
      project_id: projectId,
      limit,
      filters,
    })
    .then(result => result.calls);
}

describe('Op Flow', () => {
  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(() => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);
  });

  test('end-to-end op flow', async () => {
    // Create an inner op
    const innerOp = op((x: number) => x * 2, {name: 'innerOp'});

    // Create an outer op that calls the inner op
    const outerOp = op(
      async (x: number) => {
        const result1 = await innerOp(x);
        const result2 = await innerOp(result1);
        return result2;
      },
      {name: 'outerOp'}
    );

    // Call the outer op a couple of times
    await outerOp(5);
    await outerOp(10);

    // Wait for any pending batch processing
    await new Promise(resolve => setTimeout(resolve, 300));

    // Fetch the logged calls using the helper function
    const calls = await getCalls(inMemoryTraceServer, testProjectName);

    // Assertions
    expect(calls).toHaveLength(6); // 2 outer calls + 4 inner calls

    const outerCalls = calls.filter(call => call.op_name.includes('outerOp'));
    const innerCalls = calls.filter(call => call.op_name.includes('innerOp'));

    expect(outerCalls).toHaveLength(2);
    expect(innerCalls).toHaveLength(4);

    // Check the first outer call
    expect(outerCalls[0].inputs).toEqual({arg0: 5});
    expect(outerCalls[0].output).toBe(20);

    // Check the second outer call
    expect(outerCalls[1].inputs).toEqual({arg0: 10});
    expect(outerCalls[1].output).toBe(40);

    // Check that inner calls have correct parent_id
    innerCalls.forEach(innerCall => {
      expect(
        outerCalls.some(outerCall => outerCall.id === innerCall.parent_id)
      ).toBeTruthy();
    });

    // Check that all calls have a trace_id
    calls.forEach(call => {
      expect(call.trace_id).toBeTruthy();
    });
  });

  test('end-to-end async op flow with concurrency', async () => {
    // Create an inner async op with a random delay
    const innerAsyncOp = op(
      async (x: number) => {
        const delay = Math.random() * 50 + 10; // Random delay between 10-60ms
        await new Promise(resolve => setTimeout(resolve, delay));
        return x * 2;
      },
      {name: 'innerAsyncOp'}
    );

    // Create an outer async op that calls the inner async op
    const outerAsyncOp = op(
      async (x: number) => {
        const result1 = await innerAsyncOp(x);
        const result2 = await innerAsyncOp(result1);
        return result2;
      },
      {name: 'outerAsyncOp'}
    );

    // Call the outer async op concurrently with a small delay between calls
    const [result1, result2] = await Promise.all([
      outerAsyncOp(5),
      (async () => {
        await new Promise(resolve => setTimeout(resolve, 5)); // 5ms delay
        return outerAsyncOp(10);
      })(),
    ]);

    // Wait for any pending batch processing
    await new Promise(resolve => setTimeout(resolve, 300));

    // Fetch the logged calls using the helper function
    const calls = await getCalls(inMemoryTraceServer, testProjectName);

    // Assertions
    expect(calls).toHaveLength(6); // 2 outer calls + 4 inner calls
    expect(result1).toBe(20);
    expect(result2).toBe(40);

    const outerCalls = calls.filter(call =>
      call.op_name.includes('outerAsyncOp')
    );
    const innerCalls = calls.filter(call =>
      call.op_name.includes('innerAsyncOp')
    );

    expect(outerCalls).toHaveLength(2);
    expect(innerCalls).toHaveLength(4);

    // Check that outer calls have different start times
    const outerStartTimes = outerCalls.map(call =>
      new Date(call.started_at).getTime()
    );
    expect(outerStartTimes[0]).not.toBe(outerStartTimes[1]);

    // Check that inner calls have correct parent_id
    innerCalls.forEach(innerCall => {
      expect(
        outerCalls.some(outerCall => outerCall.id === innerCall.parent_id)
      ).toBeTruthy();
    });

    // Check that all calls have a trace_id
    calls.forEach(call => {
      expect(call.trace_id).toBeTruthy();
    });

    // Check that the duration of async calls is greater than 0
    calls.forEach(call => {
      const duration =
        new Date(call.ended_at!).getTime() -
        new Date(call.started_at).getTime();
      expect(duration).toBeGreaterThan(0);
    });

    // Check that the calls are properly nested
    outerCalls.forEach(outerCall => {
      const outerStartTime = new Date(outerCall.started_at).getTime();
      const outerEndTime = new Date(outerCall.ended_at!).getTime();
      const relatedInnerCalls = innerCalls.filter(
        innerCall => innerCall.parent_id === outerCall.id
      );
      expect(relatedInnerCalls).toHaveLength(2);
      relatedInnerCalls.forEach(innerCall => {
        const innerStartTime = new Date(innerCall.started_at).getTime();
        const innerEndTime = new Date(innerCall.ended_at!).getTime();
        expect(innerStartTime).toBeGreaterThanOrEqual(outerStartTime);
        expect(innerEndTime).toBeLessThanOrEqual(outerEndTime);
      });
    });
  });

  test('op with custom summary', async () => {
    const customSummaryOp = op((x: number) => x * 2, {
      name: 'customSummaryOp',
      summarize: result => ({doubledValue: result}),
    });

    await customSummaryOp(5);

    // Wait for any pending batch processing
    await new Promise(resolve => setTimeout(resolve, 300));

    const calls = await getCalls(inMemoryTraceServer, testProjectName);

    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('customSummaryOp');
    expect(calls[0].inputs).toEqual({arg0: 5});
    expect(calls[0].output).toBe(10);
    expect(calls[0].summary).toEqual({doubledValue: 10});
  });

  test('openai-like op with token usage summary', async () => {
    const testOpenAIChat = makeMockOpenAIChat(messages => ({
      content: messages[0].content.toUpperCase(),
    }));

    const openaiLikeOp = makeOpenAIChatCompletionsOp(
      testOpenAIChat,
      'testOpenAIChat'
    );

    await openaiLikeOp({messages: [{role: 'user', content: 'Hello, AI!'}]});

    // Wait for any pending batch processing
    await new Promise(resolve => setTimeout(resolve, 300));

    const calls = await getCalls(inMemoryTraceServer, testProjectName);

    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toContain('testOpenAIChat');
    expect(calls[0].inputs).toEqual({
      messages: [{role: 'user', content: 'Hello, AI!'}],
    });
    expect(calls[0].output).toEqual({
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
            function_call: null,
            refusal: null,
          },
          logprobs: null,
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: 2,
        completion_tokens: 2,
        total_tokens: 4,
      },
      system_fingerprint: expect.any(String),
    });
    expect(calls[0].summary).toEqual({
      usage: {
        'gpt-4o-2024-05-13': {
          requests: 1,
          completion_tokens: 2,
          prompt_tokens: 2,
          total_tokens: 4,
        },
      },
    });
  });

  test('nested op calls with summaries', async () => {
    const leafOp = op((x: number) => x, {
      name: 'leafOp',
      summarize: result => ({leaf: {count: 1, sum: result}}),
    });

    const midOp = op(
      async (x: number, y: number) => {
        const [res1, res2] = await Promise.all([leafOp(x), leafOp(y)]);
        return res1 + res2;
      },
      {
        name: 'midOp',
        summarize: result => ({mid: {count: 1, sum: result}}),
      }
    );

    const rootOp = op(
      async (a: number, b: number, c: number) => {
        const [res1, res2] = await Promise.all([midOp(a, b), leafOp(c)]);
        return res1 + res2;
      },
      {
        name: 'rootOp',
        summarize: result => ({root: {count: 1, sum: result}}),
      }
    );

    await rootOp(1, 2, 3);

    // Wait for any pending batch processing
    await new Promise(resolve => setTimeout(resolve, 300));

    const calls = await getCalls(inMemoryTraceServer, testProjectName);

    expect(calls).toHaveLength(5); // 1 root + 1 mid + 3 leaf calls

    const rootCall = calls.find(call => call.op_name.includes('rootOp'));
    expect(rootCall).toBeDefined();
    expect(rootCall?.summary).toEqual({
      root: {count: 1, sum: 6},
      mid: {count: 1, sum: 3},
      leaf: {count: 3, sum: 6}, // This is correct: 3 leaf calls, sum of 1+2+3
    });

    const midCall = calls.find(call => call.op_name.includes('midOp'));
    expect(midCall).toBeDefined();
    expect(midCall?.summary).toEqual({
      mid: {count: 1, sum: 3},
      leaf: {count: 2, sum: 3}, // This is correct: 2 leaf calls within midOp, sum of 1+2
    });

    const leafCalls = calls.filter(call => call.op_name.includes('leafOp'));
    expect(leafCalls).toHaveLength(3);

    const leafCallsUnderMid = leafCalls.filter(
      call => call.parent_id === midCall?.id
    );
    const leafCallUnderRoot = leafCalls.find(
      call => call.parent_id === rootCall?.id
    );

    expect(leafCallsUnderMid).toEqual(
      expect.arrayContaining([
        expect.objectContaining({summary: {leaf: {count: 1, sum: 1}}}),
        expect.objectContaining({summary: {leaf: {count: 1, sum: 2}}}),
      ])
    );
    expect(leafCallsUnderMid).toHaveLength(2);

    expect(leafCallUnderRoot).toEqual(
      expect.objectContaining({summary: {leaf: {count: 1, sum: 3}}})
    );

    // Ensure we have exactly these three summaries
    expect(leafCalls).toHaveLength(3);

    // Check parent-child relationships
    expect(midCall?.parent_id).toBe(rootCall?.id);
    expect(leafCallsUnderMid).toHaveLength(2);
    expect(leafCallUnderRoot).toBeDefined();

    // Ensure all leaf calls have either midCall or rootCall as parent
    leafCalls.forEach(call => {
      expect(
        call.parent_id === midCall?.id || call.parent_id === rootCall?.id
      ).toBeTruthy();
    });

    // Check that all calls have the same trace_id
    const traceId = rootCall?.trace_id;
    calls.forEach(call => {
      expect(call.trace_id).toBe(traceId);
    });
  });
});
