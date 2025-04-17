import {Netrc} from '../../utils/netrc';
import {getApiKey, getWandbConfigs} from '../../wandb/settings';
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';

jest.mock('../../utils/netrc');
jest.mock('node:fs');
jest.mock('node:path');
jest.mock('node:os');

describe('Settings', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    // Create a fresh env object without WANDB_API_KEY
    process.env = { ...originalEnv };
    delete process.env.WANDB_API_KEY;
    delete process.env.WANDB_BASE_URL;

    // Mock os.homedir
    (os.homedir as jest.Mock).mockReturnValue('/home/user');

    // Mock path.join
    (path.join as jest.Mock).mockImplementation((...args) => args.join('/'));
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('getApiKey', () => {
    test('returns API key from environment variable', () => {
      process.env.WANDB_API_KEY = 'env-api-key';
      expect(getApiKey('api.wandb.ai')).toBe('env-api-key');
    });

    test('returns API key from netrc when environment variable is not set', () => {
      const mockNetrc = {
        entries: new Map([
          ['api.wandb.ai', {password: 'netrc-api-key'}]
        ]),
      };
      (Netrc as jest.Mock).mockImplementation(() => mockNetrc);

      expect(getApiKey('api.wandb.ai')).toBe('netrc-api-key');
    });

    test('throws error when no API key is found', () => {
      const mockNetrc = {
        entries: new Map(),
      };
      (Netrc as jest.Mock).mockImplementation(() => mockNetrc);

      expect(() => getApiKey('api.wandb.ai')).toThrow('wandb API key not found');
    });

    test('handles netrc read errors gracefully', () => {
      (Netrc as jest.Mock).mockImplementation(() => {
        throw new Error('Cannot read netrc file');
      });

      expect(() => getApiKey('api.wandb.ai')).toThrow('wandb API key not found');
    });
  });

  describe('getWandbConfigs', () => {
    test('uses WANDB_BASE_URL from environment', () => {
      process.env.WANDB_BASE_URL = 'https://custom.wandb.ai';
      process.env.WANDB_API_KEY = 'test-api-key';

      const configs = getWandbConfigs();
      expect(configs).toEqual({
        apiKey: 'test-api-key',
        baseUrl: 'https://custom.wandb.ai',
        traceBaseUrl: 'https://custom.wandb.ai/traces',
        resolvedHost: 'custom.wandb.ai',
        domain: 'custom.wandb.ai',
      });
    });

    test('reads base URL from config file', () => {
      const mockConfig = `
[default]
wandb_base_url = https://custom.wandb.ai
`;
      (fs.existsSync as jest.Mock).mockReturnValue(true);
      (fs.readFileSync as jest.Mock).mockReturnValue(mockConfig);
      process.env.WANDB_API_KEY = 'test-api-key';

      const configs = getWandbConfigs();
      expect(configs.resolvedHost).toBe('custom.wandb.ai');
    });

    test('falls back to default host when no custom URL is configured', () => {
      (fs.existsSync as jest.Mock).mockReturnValue(false);
      process.env.WANDB_API_KEY = 'test-api-key';

      const configs = getWandbConfigs();
      expect(configs).toEqual({
        apiKey: 'test-api-key',
        baseUrl: 'https://api.wandb.ai',
        traceBaseUrl: 'https://trace.wandb.ai',
        resolvedHost: 'api.wandb.ai',
        domain: 'wandb.ai',
      });
    });

    test('handles config file read errors gracefully', () => {
      (fs.existsSync as jest.Mock).mockReturnValue(true);
      (fs.readFileSync as jest.Mock).mockImplementation(() => {
        throw new Error('Cannot read config file');
      });
      process.env.WANDB_API_KEY = 'test-api-key';

      const configs = getWandbConfigs();
      expect(configs.resolvedHost).toBe('api.wandb.ai');
    });
  });
});
