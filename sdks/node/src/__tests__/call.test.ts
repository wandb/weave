import * as weave from 'weave';
import {op, Op} from 'weave';

const mockOpName = 'weave://test-project-id/op/test-op';
const mockCallId = 'test-call-id';
const mockProjectId = 'test-project-id';

jest.mock('weave/clientApi', () => ({
  getGlobalClient: jest.fn(() => {
    const weaveClient = new weave.WeaveClient(
      null as any,
      null as any,
      mockProjectId
    );

    Object.assign(weaveClient, {
      pushNewCall: () => ({
        currentCall: {
          callId: mockCallId,
        },
        parentCall: null,
        newStack: [],
      }),
      createCall: (...args: any) => {
        return weave.WeaveClient.prototype.createCall.apply(weaveClient, args);
      },
      startCall: (...args: any[]) => {
        return Promise.resolve();
      },
      saveOp: (op: any, ...rest: any) => {
        op.__savedRef = Promise.resolve(op);
        op.uri = () => 'weave://test-project-id/op/test-op';
        return Promise.resolve();
      },
      runWithCallStack: async (stack: any, fn: () => any) => fn(),
      finishCall: () => Promise.resolve(),
      finishCallWithException: () => Promise.resolve(),
      settings: {shouldPrintCallLink: false},
      waitForBatchProcessing: () => Promise.resolve(),
      processBatch: () => Promise.resolve(),
    });
    return weaveClient;
  }),
}));

describe('standalone function call', () => {
  it('can use call method to get call object', async () => {
    async function myStandaloneFunction() {
      return 42;
    }
    const callDisplayName = 'test-myStandaloneFunction';

    const wrappedFn = weave.op(myStandaloneFunction, {
      callDisplayName: () => callDisplayName,
    });

    const [result, call] = await wrappedFn.invoke();
    expect(result).toBe(42);
    expect(call.op_name).toBe(mockOpName);
    expect(call.display_name).toBe(callDisplayName);
    expect(call.id).toBe(mockCallId);
    expect(call.project_id).toBe(mockProjectId);
  });
});

describe('class method call', () => {
  it('can use call method to get call object', async () => {
    class TestClass {
      @weave.op
      async myMethod() {
        return 42;
      }
    }
    const testInstance = new TestClass();

    const typedOp = testInstance.myMethod as Op<typeof testInstance.myMethod>;

    const [result, call] = await typedOp.invoke();

    expect(result).toBe(42);
    expect(call.op_name).toBe(mockOpName);
    expect(call.id).toBe(mockCallId);
    expect(call.project_id).toBe(mockProjectId);
  });
});
