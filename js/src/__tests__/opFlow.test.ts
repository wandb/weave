import { op, initWithCustomTraceServer } from '../clientApi';
import { InMemoryTraceServer } from '../inMemoryTraceServer';

// Helper function to get calls
async function getCalls(traceServer: InMemoryTraceServer, projectId: string, limit?: number, filters?: any) {
    return traceServer.calls.callsStreamQueryPost({
        project_id: projectId,
        limit,
        filters
        // Removed order_by and order_dir
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
        const innerOp = op((x: number) => x * 2, 'innerOp');

        // Create an outer op that calls the inner op
        const outerOp = op(async (x: number) => {
            const result1 = await innerOp(x);
            const result2 = await innerOp(result1);
            return result2;
        }, 'outerOp');

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
});