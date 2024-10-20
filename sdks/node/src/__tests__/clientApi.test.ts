import { getGlobalClient, init } from '../clientApi';
import { WandbServerApi } from '../wandb/wandbServerApi';
describe('Client API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('client initialization', async () => {
    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));

    const client = await init('test-project');
    expect(client).toBeDefined();
    expect(getGlobalClient()).toBe(client);
    expect(WandbServerApi).toHaveBeenCalledWith('https://api.wandb.ai', 'mock-api-key');
    // expect(TraceServerApi).toHaveBeenCalled();
  });
});
