import {Netrc} from '../../utils/netrc';
import {getApiKey, getWandbConfigs} from '../../wandb/settings';

jest.mock('../../utils/netrc');
const MockedNetrc = Netrc as jest.MockedClass<typeof Netrc>;

describe('settings', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    delete process.env.WANDB_API_KEY;
  });

  describe('getApiKey', () => {
    it('returns API key from environment variable', () => {
      process.env.WANDB_API_KEY = 'test-api-key';
      expect(getApiKey('api.wandb.ai')).toBe('test-api-key');
    });

    it('returns API key from netrc file', () => {
      MockedNetrc.prototype.entries = new Map([
        [
          'api.wandb.ai',
          {machine: 'api.wandb.ai', login: 'user', password: 'netrc-api-key'},
        ],
      ]);
      expect(getApiKey('api.wandb.ai')).toBe('netrc-api-key');
    });

    it('throws error when no API key is found', () => {
      MockedNetrc.prototype.entries = new Map();
      expect(() => getApiKey('api.wandb.ai')).toThrow(
        'wandb API key not found'
      );
    });
  });

  describe('getWandbConfigs', () => {
    it('returns correct config when netrc has entry', () => {
      // Mock successful netrc entry
      MockedNetrc.prototype.getLastEntry = jest.fn().mockReturnValue({
        machine: 'api.wandb.ai',
        login: 'user',
        password: 'test-api-key',
      });
      MockedNetrc.prototype.entries = new Map([
        [
          'api.wandb.ai',
          {machine: 'api.wandb.ai', login: 'user', password: 'test-api-key'},
        ],
      ]);

      const configs = getWandbConfigs();
      expect(configs).toEqual({
        apiKey: 'test-api-key',
        baseUrl: expect.stringContaining('api.wandb.ai'),
        traceBaseUrl: expect.stringContaining('https://trace.wandb.ai'),
        resolvedHost: 'api.wandb.ai',
        domain: expect.any(String),
      });
    });

    it('throws error when no netrc entry is found', () => {
      // Mock netrc with no entries
      MockedNetrc.prototype.getLastEntry = jest.fn().mockReturnValue(null);

      expect(() => getWandbConfigs()).toThrow(
        'Could not find entry in netrc file'
      );
    });

    it('throws error when netrc throws error', () => {
      // Mock netrc throwing error
      MockedNetrc.prototype.getLastEntry = jest.fn().mockImplementation(() => {
        throw new Error('Failed to read netrc');
      });

      expect(() => getWandbConfigs()).toThrow(
        'Could not find entry in netrc file'
      );
    });
  });
});
