import {login} from '../clientApi';
import {Api as TraceServerApi} from '../generated/traceServerApi';
import {getUrls} from '../urls';
import {Netrc} from '../utils/netrc';

// Mock dependencies
jest.mock('../utils/netrc');
jest.mock('../urls');
jest.mock('../generated/traceServerApi');

describe('login', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    console.log = jest.fn(); // Mock console.log
  });

  it('should successfully log in and save credentials', async () => {
    (getUrls as jest.Mock).mockReturnValue({
      traceBaseUrl: 'https://api.wandb.ai',
      domain: 'wandb.ai',
      host: 'api.wandb.ai',
    });

    const mockSetEntry = jest.fn();
    const mockSave = jest.fn();
    (Netrc as jest.Mock).mockImplementation(() => ({
      setEntry: mockSetEntry,
      save: mockSave,
    }));

    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      health: {
        readRootHealthGet: jest.fn().mockResolvedValue({}),
      },
    }));

    await login('test-api-key');

    expect(mockSetEntry).toHaveBeenCalledWith({
      machine: 'api.wandb.ai',
      login: 'user',
      password: 'test-api-key',
    });
    expect(mockSave).toHaveBeenCalled();
    expect(console.log).toHaveBeenCalledWith(
      'Successfully logged in. Credentials saved for api.wandb.ai'
    );
  });

  it('should throw an error if connection verification fails', async () => {
    (getUrls as jest.Mock).mockReturnValue({
      traceBaseUrl: 'https://api.wandb.ai',
      domain: 'wandb.ai',
    });

    (TraceServerApi as jest.Mock).mockImplementation(() => ({
      health: {
        readRootHealthGet: jest
          .fn()
          .mockRejectedValue(new Error('Connection failed')),
      },
    }));

    await expect(login('test-api-key')).rejects.toThrow(
      'Unable to verify connection to the weave trace server with given API Key'
    );
  });
});
