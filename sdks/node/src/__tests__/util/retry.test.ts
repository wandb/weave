import {createFetchWithRetry} from '../../utils/retry';

describe('retry', () => {
  let originalFetch: typeof global.fetch;
  const mockSuccess = {ok: true, status: 200} as Response;
  const mockFailure = {ok: false, status: 404} as Response;
  const baseDelay = 2;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    jest.resetAllMocks();
    global.fetch = originalFetch;
  });

  test('fetch happy path', async () => {
    const mockFetch = jest.fn(() => Promise.resolve(mockSuccess));
    global.fetch = mockFetch;
    const fetchWithRetry = createFetchWithRetry({baseDelay});

    const response = await fetchWithRetry('https://api.test.com');
    expect(response).toEqual(mockSuccess);
  });

  test('fetch intermittent failure then success', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce(mockFailure)
      .mockResolvedValueOnce(mockFailure)
      .mockResolvedValue(mockSuccess);
    global.fetch = mockFetch;
    const fetchWithRetry = createFetchWithRetry({baseDelay});

    const response = await fetchWithRetry('https://api.test.com');
    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(response).toEqual(mockSuccess);
  });

  test('fetch retry failure', async () => {
    const maxRetries = 3;

    const mockFetch = jest.fn().mockResolvedValue(mockFailure);
    global.fetch = mockFetch;
    const fetchWithRetry = createFetchWithRetry({maxRetries, baseDelay});

    const response = await fetchWithRetry('https://api.test.com');
    expect(mockFetch).toHaveBeenCalledTimes(maxRetries + 1);
    expect(response).toEqual(mockFailure);
  });

  test('fetch exception then success', async () => {
    const mockFetch = jest
      .fn()
      .mockRejectedValueOnce(new Error('test'))
      .mockResolvedValue(mockSuccess);
    global.fetch = mockFetch;
    const fetchWithRetry = createFetchWithRetry({baseDelay});

    const response = await fetchWithRetry('https://api.test.com');
    expect(mockFetch).toHaveBeenCalledTimes(2);
    expect(response).toEqual(mockSuccess);
  });
});
