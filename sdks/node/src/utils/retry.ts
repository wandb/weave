type RetryOptions = {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  maxRetryTime?: number;
  retryOnStatus?: (status: number) => boolean;
};

/**
 * Parses a `Retry-After` header value (seconds, or an HTTP date) into a
 * millisecond delay. Returns `null` when the header is absent or
 * unparseable, so the caller can fall back to exponential backoff.
 */
function parseRetryAfterMs(response: Response): number | null {
  const header = response.headers?.get?.('retry-after');
  if (!header) {
    return null;
  }
  const seconds = Number(header);
  if (Number.isFinite(seconds)) {
    return Math.max(0, seconds * 1000);
  }
  const dateMs = Date.parse(header);
  if (!Number.isNaN(dateMs)) {
    return Math.max(0, dateMs - Date.now());
  }
  return null;
}

export function createFetchWithRetry(options: RetryOptions = {}) {
  const {
    maxRetries = 5,
    baseDelay = 100,
    maxDelay = 10000,
    maxRetryTime = 10000,
    retryOnStatus = (status: number) => status !== 429 && status !== 500,
  } = options;

  return async function fetchWithRetry(
    ...fetchParams: Parameters<typeof fetch>
  ): Promise<Response> {
    let attempt = 0;

    while (attempt <= maxRetries) {
      const startTime = Date.now();
      try {
        const response = await fetch(...fetchParams);

        // A 429 with a `Retry-After` longer than we're willing to wait is
        // quota/billing exhaustion, not transient pressure: retrying just
        // amplifies load against a limit that isn't about to lift. Surface
        // it to the caller immediately instead of burning the retry budget.
        const retryAfterMs =
          response.status === 429 ? parseRetryAfterMs(response) : null;
        const quotaExhausted = retryAfterMs !== null && retryAfterMs > maxDelay;

        if (
          response.ok ||
          !retryOnStatus(response.status) ||
          quotaExhausted ||
          attempt === maxRetries ||
          Date.now() - startTime > maxRetryTime
        ) {
          // Always return the response, even if it's not ok
          return response;
        }

        // Prefer the server's own `Retry-After` when it gave us one; it
        // knows its rate-limit window better than our exponential guess
        // does. Fall back to exponential backoff otherwise.
        const delay =
          retryAfterMs !== null
            ? Math.min(retryAfterMs, maxDelay)
            : Math.min(baseDelay * 2 ** attempt, maxDelay);
        console.log(
          `Return code: ${response.status}. Retrying fetch after ${delay}ms`
        );
        await new Promise(resolve => setTimeout(resolve, delay));
        attempt++;
      } catch (error) {
        if (attempt === maxRetries || Date.now() - startTime > maxRetryTime) {
          // Rethrow the original error
          throw error;
        }
        // Exponential backoff delay
        const delay = Math.min(baseDelay * 2 ** attempt, maxDelay);
        console.log(`Exception ${error} Retrying fetch after ${delay}ms`);
        await new Promise(resolve => setTimeout(resolve, delay));
        attempt++;
      }
    }
    throw new Error("Failed to fetch. Shouldn't get here");
  };
}
