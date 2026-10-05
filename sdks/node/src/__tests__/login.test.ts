import {login} from '../clientApi';
import {createTraceServerClient} from '../traceServerClient';
import {getUrls} from '../urls';
import {Netrc} from '../utils/netrc';
import {stainlessPromise} from './helpers/stainlessPromise';

jest.mock('../utils/netrc');
jest.mock('../urls');
jest.mock('../traceServerClient', () => ({
  createTraceServerClient: jest.fn(),
}));

describe('login', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    console.log = jest.fn();
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

    (createTraceServerClient as jest.Mock).mockImplementation(() => ({
      services: {
        healthCheck: jest.fn().mockReturnValue(stainlessPromise({})),
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

    (createTraceServerClient as jest.Mock).mockImplementation(() => ({
      services: {
        healthCheck: jest
          .fn()
          .mockRejectedValue(new Error('Connection failed')),
      },
    }));

    await expect(login('test-api-key')).rejects.toThrow(
      'Unable to verify connection to the weave trace server with given API Key'
    );
  });
});
