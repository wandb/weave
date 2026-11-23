import {
  createFetchWithRetry,
  isQuotaExhausted429,
  parseRetryAfterMs,
} from '../utils/retry';

describe('parseRetryAfterMs', () => {
  it('parses delta-seconds values', () => {
    expect(parseRetryAfterMs('2')).toBe(2000);
    expect(parseRetryAfterMs('0.5')).toBe(500);
    expect(parseRetryAfterMs('0')).toBe(0);
  });

  it('parses HTTP-date values relative to now', () => {
    const now = Date.UTC(2026, 10, 23, 12, 0, 0);
    const future = new Date(now + 4000).toUTCString();
    expect(parseRetryAfterMs(future, now)).toBe(4000);

    const past = new Date(now - 5000).toUTCString();
    expect(parseRetryAfterMs(past, now)).toBe(0);
  });

  it('returns null for absent or invalid headers', () => {
    expect(parseRetryAfterMs(null)).toBeNull();
    expect(parseRetryAfterMs('')).toBeNull();
    expect(parseRetryAfterMs('not-a-date')).toBeNull();
  });
});

describe('isQuotaExhausted429', () => {
  it('detects quota/billing exhaustion 429s without consuming the body', async () => {
    const payload = JSON.stringify({
      error: {
        code: 'insufficient_quota',
        message: 'You exceeded your current quota',
      },
    });
    const res = new Response(payload, {status: 429});
    expect(await isQuotaExhausted429(res)).toBe(true);
    // Original response body must remain readable for caller
    expect(await res.text()).toBe(payload);
  });

  it('returns false for transient rate-limit 429s', async () => {
    const res = new Response('rate limit exceeded, try again shortly', {
      status: 429,
    });
    expect(await isQuotaExhausted429(res)).toBe(false);
  });
});

describe('createFetchWithRetry', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it('does not retry quota-exhausted 429 responses', async () => {
    const mockFetch = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({error: {code: 'insufficient_quota'}}), {
        status: 429,
      })
    );
    global.fetch = mockFetch as unknown as typeof fetch;

    const retryFetch = createFetchWithRetry({
      maxRetries: 3,
      baseDelay: 1,
      maxDelay: 10,
      retryOnStatus: status => status === 429 || status >= 500,
    });

    const response = await retryFetch('https://trace.wandb.ai/call/start');
    expect(response.status).toBe(429);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(await response.text()).toContain('insufficient_quota');
  });

  it('honors Retry-After on transient 429 and caps by maxDelay', async () => {
    const delays: number[] = [];
    const origSetTimeout = global.setTimeout;
    jest.spyOn(global, 'setTimeout').mockImplementation(((
      fn: (...args: unknown[]) => void,
      ms?: number
    ) => {
      delays.push(ms ?? 0);
      return origSetTimeout(fn, 0);
    }) as typeof setTimeout);

    const mockFetch = jest
      .fn()
      .mockResolvedValueOnce(
        new Response('too many requests', {
          status: 429,
          headers: {'Retry-After': '0.25'},
        })
      )
      .mockResolvedValueOnce(
        new Response('too many requests', {
          status: 429,
          headers: {'Retry-After': '120'},
        })
      )
      .mockResolvedValueOnce(new Response('ok', {status: 200}));
    global.fetch = mockFetch as unknown as typeof fetch;

    const retryFetch = createFetchWithRetry({
      maxRetries: 3,
      baseDelay: 10,
      maxDelay: 500,
    });

    const response = await retryFetch('https://trace.wandb.ai/call/start');
    expect(response.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(delays).toEqual([250, 500]);
  });

  it('does not retry 400 client errors under default retryOnStatus', async () => {
    const mockFetch = jest
      .fn()
      .mockResolvedValue(new Response('bad request', {status: 400}));
    global.fetch = mockFetch as unknown as typeof fetch;

    const retryFetch = createFetchWithRetry({maxRetries: 3, baseDelay: 1});
    const response = await retryFetch('https://trace.wandb.ai/call/start');
    expect(response.status).toBe(400);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });
});
