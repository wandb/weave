import { op, initWithCustomTraceServer } from '../clientApi';
import { InMemoryTraceServer } from '../inMemoryTraceServer';

// Helper function to get calls
async function getCalls(traceServer: InMemoryTraceServer, projectId: string, limit?: number, filters?: any) {
    return traceServer.calls.callsStreamQueryPost({
        project_id: projectId,
        limit,
        filters
    }).then(result => result.calls);
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
        const innerOp = op((x: number) => x * 2, { name: 'innerOp' });

        // Create an outer op that calls the inner op
        const outerOp = op(async (x: number) => {
            const result1 = await innerOp(x);
            const result2 = await innerOp(result1);
            return result2;
        }, { name: 'outerOp' });

        // Call the outer op a couple of times
        await outerOp(5);
        await outerOp(10);

        // Wait for any pending batch processing
        await new Promise(resolve => setTimeout(resolve, 300));

        // Fetch the logged calls using the helper function
        const calls = await getCalls(inMemoryTraceServer, testProjectName);

        // Assertions
        expect(calls).toHaveLength(6); // 2 outer calls + 4 inner calls

        const outerCalls = calls.filter(call => call.op_name === 'outerOp');
        const innerCalls = calls.filter(call => call.op_name === 'innerOp');

        expect(outerCalls).toHaveLength(2);
        expect(innerCalls).toHaveLength(4);

        // Check the first outer call
        expect(outerCalls[0].inputs).toEqual({ arg0: 5 });
        expect(outerCalls[0].output).toBe(20);

        // Check the second outer call
        expect(outerCalls[1].inputs).toEqual({ arg0: 10 });
        expect(outerCalls[1].output).toBe(40);

        // Check that inner calls have correct parent_id
        innerCalls.forEach(innerCall => {
            expect(outerCalls.some(outerCall => outerCall.id === innerCall.parent_id)).toBeTruthy();
        });

        // Check that all calls have a trace_id
        calls.forEach(call => {
            expect(call.trace_id).toBeTruthy();
        });
    });

    test('end-to-end async op flow with concurrency', async () => {
        // Create an inner async op with a random delay
        const innerAsyncOp = op(async (x: number) => {
            const delay = Math.random() * 50 + 10; // Random delay between 10-60ms
            await new Promise(resolve => setTimeout(resolve, delay));
            return x * 2;
        }, { name: 'innerAsyncOp' });

        // Create an outer async op that calls the inner async op
        const outerAsyncOp = op(async (x: number) => {
            const result1 = await innerAsyncOp(x);
            const result2 = await innerAsyncOp(result1);
            return result2;
        }, { name: 'outerAsyncOp' });

        // Call the outer async op concurrently
        const [result1, result2] = await Promise.all([
            outerAsyncOp(5),
            outerAsyncOp(10)
        ]);

        // Wait for any pending batch processing
        await new Promise(resolve => setTimeout(resolve, 300));

        // Fetch the logged calls using the helper function
        const calls = await getCalls(inMemoryTraceServer, testProjectName);

        // Assertions
        expect(calls).toHaveLength(6); // 2 outer calls + 4 inner calls
        expect(result1).toBe(20);
        expect(result2).toBe(40);

        const outerCalls = calls.filter(call => call.op_name === 'outerAsyncOp');
        const innerCalls = calls.filter(call => call.op_name === 'innerAsyncOp');

        expect(outerCalls).toHaveLength(2);
        expect(innerCalls).toHaveLength(4);

        // Check that outer calls have different start times
        const outerStartTimes = outerCalls.map(call => new Date(call.started_at).getTime());
        expect(outerStartTimes[0]).not.toBe(outerStartTimes[1]);

        // Check that inner calls have correct parent_id
        innerCalls.forEach(innerCall => {
            expect(outerCalls.some(outerCall => outerCall.id === innerCall.parent_id)).toBeTruthy();
        });

        // Check that all calls have a trace_id
        calls.forEach(call => {
            expect(call.trace_id).toBeTruthy();
        });

        // Check that the duration of async calls is greater than 0
        calls.forEach(call => {
            const duration = new Date(call.ended_at!).getTime() - new Date(call.started_at).getTime();
            expect(duration).toBeGreaterThan(0);
        });

        // Check that the calls are properly nested
        outerCalls.forEach(outerCall => {
            const outerStartTime = new Date(outerCall.started_at).getTime();
            const outerEndTime = new Date(outerCall.ended_at!).getTime();
            const relatedInnerCalls = innerCalls.filter(innerCall => innerCall.parent_id === outerCall.id);
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
        const customSummaryOp = op(
            (x: number) => x * 2,
            {
                name: 'customSummaryOp',
                summarize: (result) => ({ doubledValue: result })
            }
        );

        await customSummaryOp(5);

        // Wait for any pending batch processing
        await new Promise(resolve => setTimeout(resolve, 300));

        const calls = await getCalls(inMemoryTraceServer, testProjectName);

        expect(calls).toHaveLength(1);
        expect(calls[0].op_name).toBe('customSummaryOp');
        expect(calls[0].inputs).toEqual({ arg0: 5 });
        expect(calls[0].output).toBe(10);
        expect(calls[0].summary).toEqual({ doubledValue: 10 });
    });

    test('openai-like op with token usage summary', async () => {
        const openaiLikeOp = op(
            async (prompt: string) => {
                // Simulate OpenAI API response
                return {
                    model: 'gpt-3.5-turbo',
                    usage: { total_tokens: prompt.length * 2 }, // Simplified token count
                    choices: [{ message: { content: prompt.toUpperCase() } }]
                };
            },
            {
                name: 'openai.chat.completions.create',
                summarize: (result) => ({
                    usage: {
                        [result.model]: result.usage
                    }
                })
            }
        );

        await openaiLikeOp('Hello, AI!');

        // Wait for any pending batch processing
        await new Promise(resolve => setTimeout(resolve, 300));

        const calls = await getCalls(inMemoryTraceServer, testProjectName);

        expect(calls).toHaveLength(1);
        expect(calls[0].op_name).toBe('openai.chat.completions.create');
        expect(calls[0].inputs).toEqual({ arg0: 'Hello, AI!' });
        expect(calls[0].output).toEqual({
            model: 'gpt-3.5-turbo',
            usage: { total_tokens: 20 },
            choices: [{ message: { content: 'HELLO, AI!' } }]
        });
        expect(calls[0].summary).toEqual({
            usage: {
                'gpt-3.5-turbo': { requests: 1, total_tokens: 20 }
            }
        });
    });
});