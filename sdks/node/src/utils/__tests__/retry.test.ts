import {createFetchWithRetry, parseRetryAfterMs} from '../retry';

// ---------------------------------------------------------------------------
// parseRetryAfterMs
// ---------------------------------------------------------------------------

function headersFrom(record: Record<string, string>): Headers {
  return new Headers(record);
}

describe('parseRetryAfterMs', () => {
  test('returns null when Retry-After header is absent', () => {
    expect(parseRetryAfterMs(headersFrom({}))).toBeNull();
  });

  test('returns milliseconds for a positive numeric value', () => {
    expect(parseRetryAfterMs(headersFrom({'retry-after': '30'}))).toBe(30_000);
    expect(parseRetryAfterMs(headersFrom({'retry-after': '0'}))).toBe(0);
  });

  test('returns null for a negative numeric value', () => {
    // Negative values are invalid per RFC 7231 and must not be used as a delay
    expect(parseRetryAfterMs(headersFrom({'retry-after': '-1'}))).toBeNull();
  });

  test('returns positive ms for a future HTTP date', () => {
    const future = new Date(Date.now() + 45_000).toUTCString();
    const result = parseRetryAfterMs(headersFrom({'retry-after': future}));
    // Allow ±2 s for test execution time
    expect(result).toBeGreaterThan(43_000);
    expect(result).toBeLessThan(47_000);
  });

  test('clamps past HTTP dates to 0', () => {
    const past = new Date(Date.now() - 5_000).toUTCString();
    expect(parseRetryAfterMs(headersFrom({'retry-after': past}))).toBe(0);
  });

  test('returns null for an unparseable string', () => {
    expect(
      parseRetryAfterMs(headersFrom({'retry-after': 'not-a-date'}))
    ).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// createFetchWithRetry — 429 Retry-After classification
// ---------------------------------------------------------------------------

function make429(retryAfter?: string): Response {
  const headers = new Headers({'content-type': 'application/json'});
  if (retryAfter !== undefined) {
    headers.set('retry-after', retryAfter);
  }
  return new Response(null, {status: 429, headers});
}

function makeOk(): Response {
  return new Response(null, {status: 200});
}

describe('createFetchWithRetry — 429 behaviour', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('long Retry-After (>60 s) returns immediately without retrying', async () => {
    const mockFetch = jest.fn().mockResolvedValue(make429('600'));
    jest.spyOn(global, 'fetch').mockImplementation(mockFetch);

    const fetchWithRetry = createFetchWithRetry({
      retryOnStatus: () => true,
    });

    const responsePromise = fetchWithRetry('https://example.com');
    // Advance timers — no setTimeout should fire for the quota-exhaustion case
    await jest.runAllTimersAsync();
    const response = await responsePromise;

    expect(response.status).toBe(429);
    expect(mockFetch).toHaveBeenCalledTimes(1); // no retries
  });

  test('short Retry-After (≤60 s) uses the server-specified delay, not exponential backoff', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce(make429('30'))
      .mockResolvedValue(makeOk());
    jest.spyOn(global, 'fetch').mockImplementation(mockFetch);

    // Capture setTimeout calls to inspect the actual delay used
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout');

    const fetchWithRetry = createFetchWithRetry({
      retryOnStatus: () => true,
      maxDelay: 60_000, // above 30 s so the cap does not mask the assertion
    });

    const responsePromise = fetchWithRetry('https://example.com');
    await jest.runAllTimersAsync();
    const response = await responsePromise;

    expect(response.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(2);

    // The retry delay must be the server-specified 30 s (30000 ms).
    // Exponential backoff at attempt 0 would be baseDelay * 2^0 = 100 ms — a clearly different value.
    const observedDelays = setTimeoutSpy.mock.calls.map(([, delay]) => delay);
    expect(observedDelays).toContain(30_000);
  });

  test('no Retry-After header retries with exponential backoff', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce(make429())
      .mockResolvedValue(makeOk());
    jest.spyOn(global, 'fetch').mockImplementation(mockFetch);

    const fetchWithRetry = createFetchWithRetry({
      retryOnStatus: () => true,
    });

    const responsePromise = fetchWithRetry('https://example.com');
    await jest.runAllTimersAsync();
    const response = await responsePromise;

    expect(response.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  test('retryOnStatus returning false for 429 skips Retry-After logic entirely', async () => {
    const mockFetch = jest.fn().mockResolvedValue(make429('600'));
    jest.spyOn(global, 'fetch').mockImplementation(mockFetch);

    // Caller explicitly opts out of retrying 429
    const fetchWithRetry = createFetchWithRetry({
      retryOnStatus: (status: number) => status !== 429,
    });

    const responsePromise = fetchWithRetry('https://example.com');
    await jest.runAllTimersAsync();
    const response = await responsePromise;

    expect(response.status).toBe(429);
    expect(mockFetch).toHaveBeenCalledTimes(1); // returned immediately
  });

  test('negative Retry-After value is treated as no header (exponential backoff)', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce(make429('-1'))
      .mockResolvedValue(makeOk());
    jest.spyOn(global, 'fetch').mockImplementation(mockFetch);

    const fetchWithRetry = createFetchWithRetry({
      retryOnStatus: () => true,
    });

    const responsePromise = fetchWithRetry('https://example.com');
    await jest.runAllTimersAsync();
    const response = await responsePromise;

    expect(response.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(2); // retried via backoff
  });
});
