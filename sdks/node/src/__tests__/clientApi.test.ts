import {init, requireGlobalClient} from '../clientApi';
import {getWandbConfigs} from '../wandb/settings';
import {WandbServerApi} from '../wandb/wandbServerApi';

jest.mock('../wandb/wandbServerApi');
jest.mock('../wandb/settings');

describe('Client API', () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Mock getWandbConfigs
    (getWandbConfigs as jest.Mock).mockReturnValue({
      apiKey: 'mock-api-key',
      baseUrl: 'https://api.wandb.ai',
      traceBaseUrl: 'https://trace.wandb.ai',
      domain: 'api.wandb.ai',
      host: 'api.wandb.ai',
    });

    // Mock WandbServerApi
    (WandbServerApi as jest.Mock).mockImplementation(() => ({
      defaultEntityName: jest.fn().mockResolvedValue('test-entity'),
    }));
  });

  describe('initialization', () => {
    test('initializes with project name', async () => {
      const client = await init('test-project');
      const gottenClient = requireGlobalClient();

      expect(gottenClient).toBeDefined();
      expect(gottenClient).toBe(client);
      expect(WandbServerApi).toHaveBeenCalledWith(
        'https://api.wandb.ai',
        'mock-api-key'
      );
      expect(gottenClient.projectId).toBe('test-entity/test-project');
    });

    test('initializes with entity/project', async () => {
      const client = await init('custom-entity/test-project');
      const gottenClient = requireGlobalClient();

      expect(gottenClient).toBeDefined();
      expect(gottenClient).toBe(client);
      expect(WandbServerApi).toHaveBeenCalledWith(
        'https://api.wandb.ai',
        'mock-api-key'
      );
      expect(gottenClient.projectId).toBe('custom-entity/test-project');
    });
  });
});
