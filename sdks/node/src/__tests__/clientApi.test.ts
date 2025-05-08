import {init, requireGlobalClient, login} from '../clientApi';
import {getWandbConfigs} from '../wandb/settings';
import {WandbServerApi} from '../wandb/wandbServerApi';
import {Api as TraceServerApi} from '../generated/traceServerApi';
import {Netrc} from '../utils/netrc';

jest.mock('../wandb/wandbServerApi');
jest.mock('../wandb/settings');
jest.mock('../generated/traceServerApi');
jest.mock('../utils/netrc');

describe('Client API', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...originalEnv };

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

    // Mock TraceServerApi
    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      health: {
        readRootHealthGet: jest.fn().mockResolvedValue({}),
      },
    }));

    // Mock Netrc
    (Netrc as jest.Mock).mockImplementation(() => ({
      entries: new Map(),
      setEntry: jest.fn(),
      save: jest.fn(),
    }));
  });

  afterEach(() => {
    process.env = originalEnv;
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

  describe('login', () => {
    test('successfully logs in and saves to netrc', async () => {
      const mockNetrc = {
        entries: new Map(),
        setEntry: jest.fn(),
        save: jest.fn(),
      };
      (Netrc as jest.Mock).mockImplementation(() => mockNetrc);

      await login('test-api-key');

      expect(mockNetrc.setEntry).toHaveBeenCalledWith({
        machine: 'api.wandb.ai',
        login: 'user',
        password: 'test-api-key',
      });
      expect(mockNetrc.save).toHaveBeenCalled();
      expect(process.env.WANDB_API_KEY).toBe('test-api-key');
    });

    test('continues if netrc save fails', async () => {
      const mockNetrc = {
        entries: new Map(),
        setEntry: jest.fn(),
        save: jest.fn().mockImplementation(() => {
          throw new Error('Cannot write to file system');
        }),
      };
      (Netrc as jest.Mock).mockImplementation(() => mockNetrc);

      await login('test-api-key');

      expect(mockNetrc.setEntry).toHaveBeenCalled();
      expect(process.env.WANDB_API_KEY).toBe('test-api-key');
    });

    test('throws error if API key is not provided', async () => {
      await expect(login('')).rejects.toThrow('API key is required for login');
    });

    test('throws error if connection verification fails', async () => {
      (TraceServerApi as jest.Mock).mockImplementation(() => ({
        health: {
          readRootHealthGet: jest.fn().mockRejectedValue(new Error('Connection failed')),
        },
      }));

      await expect(login('test-api-key')).rejects.toThrow(
        'Unable to verify connection to the weave trace server'
      );
    });

    test('uses custom host when provided', async () => {
      const mockNetrc = {
        entries: new Map(),
        setEntry: jest.fn(),
        save: jest.fn(),
      };
      (Netrc as jest.Mock).mockImplementation(() => mockNetrc);

      await login('test-api-key', 'custom.wandb.ai');

      expect(mockNetrc.setEntry).toHaveBeenCalledWith({
        machine: 'custom.wandb.ai',
        login: 'user',
        password: 'test-api-key',
      });
    });
  });
});
