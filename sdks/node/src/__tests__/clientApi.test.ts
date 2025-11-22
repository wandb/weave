import {init, requireGlobalClient, login, attributes} from '../clientApi';
import {getWandbConfigs} from '../wandb/settings';
import {WandbServerApi} from '../wandb/wandbServerApi';
import {Api as TraceServerApi} from '../generated/traceServerApi';
import {Netrc} from '../utils/netrc';
import {op} from '../op';

jest.mock('../wandb/wandbServerApi');
jest.mock('../wandb/settings');
jest.mock('../generated/traceServerApi');
jest.mock('../utils/netrc');

describe('Client API', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = {...originalEnv};

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
          readRootHealthGet: jest
            .fn()
            .mockRejectedValue(new Error('Connection failed')),
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

  describe('attributes', () => {
    test('attributes context manager sets attributes on calls', async () => {
      const client = await init('test-project');
      let capturedAttributes: Record<string, any> | undefined;

      // Mock createCall to capture attributes
      const originalCreateCall = client.createCall.bind(client);
      client.createCall = jest.fn(async (...args: any[]) => {
        capturedAttributes = args[9]; // attributes is the 10th parameter (index 9)
        return Promise.resolve();
      });

      const myOp = op(async (name: string) => {
        return `Hello ${name}`;
      });

      // Call op with attributes
      await attributes({env: 'production', user: 'alice'}, async () => {
        await myOp('World');
      });

      expect(capturedAttributes).toBeDefined();
      expect(capturedAttributes).toEqual({
        env: 'production',
        user: 'alice',
      });
    });

    test('attributes merges with existing attributes', async () => {
      const client = await init('test-project');
      let capturedAttributes: Record<string, any> | undefined;

      // Mock createCall to capture attributes
      client.createCall = jest.fn(async (...args: any[]) => {
        capturedAttributes = args[9]; // attributes is the 10th parameter (index 9)
        return Promise.resolve();
      });

      const myOp = op(async (name: string) => {
        return `Hello ${name}`;
      });

      // Nested attributes should merge
      await attributes({env: 'production'}, async () => {
        await attributes({user: 'alice'}, async () => {
          await myOp('World');
        });
      });

      expect(capturedAttributes).toBeDefined();
      expect(capturedAttributes).toEqual({
        env: 'production',
        user: 'alice',
      });
    });

    test('attributes overwrites values with same key', async () => {
      const client = await init('test-project');
      let capturedAttributes: Record<string, any> | undefined;

      // Mock createCall to capture attributes
      client.createCall = jest.fn(async (...args: any[]) => {
        capturedAttributes = args[9]; // attributes is the 10th parameter (index 9)
        return Promise.resolve();
      });

      const myOp = op(async (name: string) => {
        return `Hello ${name}`;
      });

      // Inner attributes should overwrite outer ones
      await attributes({env: 'production', user: 'alice'}, async () => {
        await attributes({env: 'staging'}, async () => {
          await myOp('World');
        });
      });

      expect(capturedAttributes).toBeDefined();
      expect(capturedAttributes).toEqual({
        env: 'staging',
        user: 'alice',
      });
    });

    test('attributes are isolated across concurrent calls', async () => {
      const client = await init('test-project');
      const capturedAttributes: Record<string, any>[] = [];

      // Mock createCall to capture all attributes
      client.createCall = jest.fn(async (...args: any[]) => {
        capturedAttributes.push({...args[9]}); // Copy attributes
        return Promise.resolve();
      });

      const myOp = op(async (id: string) => {
        // Add a small delay to simulate async work
        await new Promise(resolve => setTimeout(resolve, 10));
        return `Done ${id}`;
      });

      // Run multiple attribute contexts concurrently
      await Promise.all([
        attributes({user: 'alice', session: 'a1'}, async () => {
          await myOp('1');
        }),
        attributes({user: 'bob', session: 'b2'}, async () => {
          await myOp('2');
        }),
        attributes({user: 'charlie', session: 'c3'}, async () => {
          await myOp('3');
        }),
      ]);

      // Each call should have its correct attributes (not clobbered)
      expect(capturedAttributes).toHaveLength(3);

      // Extract all users and sessions
      const users = capturedAttributes.map(a => a.user);
      const sessions = capturedAttributes.map(a => a.session);

      // All unique values should be present
      expect(users).toContain('alice');
      expect(users).toContain('bob');
      expect(users).toContain('charlie');
      expect(sessions).toContain('a1');
      expect(sessions).toContain('b2');
      expect(sessions).toContain('c3');

      // Each should have matching pairs (alice with a1, bob with b2, etc)
      const aliceAttrs = capturedAttributes.find(a => a.user === 'alice');
      expect(aliceAttrs?.session).toBe('a1');

      const bobAttrs = capturedAttributes.find(a => a.user === 'bob');
      expect(bobAttrs?.session).toBe('b2');

      const charlieAttrs = capturedAttributes.find(a => a.user === 'charlie');
      expect(charlieAttrs?.session).toBe('c3');
    });

    test('attributes works without initialized client', async () => {
      // Should not throw when client is not initialized
      const result = await attributes({env: 'test'}, async () => {
        return 'success';
      });

      expect(result).toBe('success');
    });
  });
});
