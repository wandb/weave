import {init, requireGlobalClient} from '../clientApi';
import {getApiKey} from '../wandb/settings';
import {WandbServerApi} from '../wandb/wandbServerApi';

jest.mock('../wandb/wandbServerApi');
jest.mock('../wandb/settings');

describe('Client API', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('client initialization', async () => {
    (getApiKey as jest.Mock).mockReturnValue('mock-api-key');

    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));

    const client = await init('test-project');
    const gottenClient = requireGlobalClient();

    expect(gottenClient).toBeDefined();
    expect(gottenClient).toBe(client);
    expect(WandbServerApi).toHaveBeenCalledWith(
      'https://api.wandb.ai',
      'mock-api-key'
    );
    expect(gottenClient.projectId).toEqual('test-entity/test-project');
  });
});
