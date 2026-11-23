type RetryOptions = {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  maxRetryTime?: number;
  retryOnStatus?: (status: number) => boolean;
};

const QUOTA_EXHAUSTED_PATTERNS = [
  /insufficient[_\s-]?quota/i,
  /quota[_\s-]?exceeded/i,
  /billing[_\s-]?(?:hard[_\s-]?)?limit/i,
  /exceeded\s+your\s+current\s+quota/i,
  /account\s+is\s+not\s+active/i,
];

/**
 * Parse an HTTP `Retry-After` header (delta-seconds or HTTP-date) into
 * milliseconds. Returns `null` when absent or unparseable.
 */
export function parseRetryAfterMs(
  headerValue: string | null,
  now: number = Date.now()
): number | null {
  if (!headerValue) {
    return null;
  }
  const trimmed = headerValue.trim();
  if (!trimmed) {
    return null;
  }
  if (/^\d+(?:\.\d+)?$/.test(trimmed)) {
    const seconds = Number(trimmed);
    return Number.isFinite(seconds)
      ? Math.max(0, Math.round(seconds * 1000))
      : null;
  }
  const parsedDate = Date.parse(trimmed);
  if (Number.isNaN(parsedDate)) {
    return null;
  }
  return Math.max(0, parsedDate - now);
}

/**
 * Inspect a cloned 429 response body to detect non-retryable quota or billing
 * exhaustion so the SDK fails fast instead of amplifying retries.
 */
export async function isQuotaExhausted429(
  response: Response
): Promise<boolean> {
  if (response.status !== 429) {
    return false;
  }
  try {
    const body = await response.clone().text();
    if (!body) {
      return false;
    }
    return QUOTA_EXHAUSTED_PATTERNS.some(pattern => pattern.test(body));
  } catch {
    return false;
  }
}

export function createFetchWithRetry(options: RetryOptions = {}) {
  const {
    maxRetries = 5,
    baseDelay = 100,
    maxDelay = 10000,
    maxRetryTime = 10000,
    retryOnStatus = (status: number) =>
      status === 429 || (status >= 500 && status < 600),
  } = options;

  return async function fetchWithRetry(
    ...fetchParams: Parameters<typeof fetch>
  ): Promise<Response> {
    let attempt = 0;
    const startTime = Date.now();

    while (attempt <= maxRetries) {
      try {
        const response = await fetch(...fetchParams);

        if (
          response.ok ||
          !retryOnStatus(response.status) ||
          attempt === maxRetries ||
          Date.now() - startTime > maxRetryTime
        ) {
          // Always return the response, even if it's not ok
          return response;
        }

        if (response.status === 429 && (await isQuotaExhausted429(response))) {
          // Do not retry hard quota/billing exhaustion 429s
          return response;
        }

        const retryAfterMs =
          response.status === 429 || response.status === 503
            ? parseRetryAfterMs(response.headers?.get?.('retry-after') ?? null)
            : null;
        const backoffDelay = Math.min(baseDelay * 2 ** attempt, maxDelay);
        const delay =
          retryAfterMs !== null
            ? Math.min(retryAfterMs, maxDelay)
            : backoffDelay;
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
