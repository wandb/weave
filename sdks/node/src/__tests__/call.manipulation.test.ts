import * as weave from 'weave';
import {op, Op} from 'weave';
import {CallState, InternalCall} from 'weave/call';
import {getGlobalClient} from 'weave/clientApi';

const mockCallId = 'test-call-id';
const mockProjectId = 'test-project-id';

const mockUpdateCall = jest.fn();

jest.mock('weave/clientApi', () => ({
  getGlobalClient: jest.fn(() => {
    const weaveClient = new weave.WeaveClient(
      null as any,
      null as any,
      mockProjectId
    );

    Object.assign(weaveClient, {
      getCall: async (callId: string) => {
        const internalCall = new InternalCall();
        internalCall.updateWithCallSchemaData({
          id: callId,
        });

        internalCall.state = CallState.finished;

        return internalCall.proxy;
      },
      updateCall: mockUpdateCall,
    });
    return weaveClient;
  }),
}));

beforeEach(() => {
  mockUpdateCall.mockClear();
});

describe('get call handle', () => {
  it('can use the handle to reset display name', async () => {
    const client = getGlobalClient();
    const call = await client!.getCall(mockCallId);

    expect(call.id).toBe(mockCallId);

    await call.setDisplayName('test-display-name');

    expect(mockUpdateCall).toHaveBeenCalledWith(
      mockCallId,
      'test-display-name'
    );
  });
});
