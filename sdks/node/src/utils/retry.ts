// Retry-After values above this threshold (in seconds) indicate quota/billing
// exhaustion — do not retry in that case.
const RETRY_AFTER_STOP_THRESHOLD_SECONDS = 60;

type RetryOptions = {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  maxRetryTime?: number;
  retryOnStatus?: (status: number) => boolean;
};

/**
 * Parse the Retry-After header and return the delay in milliseconds.
 * Returns null if the header is absent or unparseable.
 */
export function parseRetryAfterMs(headers: Headers): number | null {
  const retryAfter = headers.get('retry-after');
  if (!retryAfter) return null;

  // Retry-After can be a number of seconds or an HTTP date.
  // Handle the numeric case first — if the value is a valid number but
  // negative, reject it explicitly rather than letting it fall through to
  // the date parser (e.g. new Date('-1') parses as 1 BCE and returns 0).
  const seconds = Number(retryAfter);
  if (!isNaN(seconds)) {
    return seconds >= 0 ? seconds * 1000 : null;
  }

  const date = new Date(retryAfter);
  if (!isNaN(date.getTime())) {
    return Math.max(0, date.getTime() - Date.now());
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

        // For 429 responses, inspect Retry-After to classify the rate limit,
        // but only if the caller has not disabled retries for this status code.
        // - Long Retry-After (> threshold) → quota/billing exhaustion, do not retry
        // - Short Retry-After → transient pressure, wait the specified duration
        // - No Retry-After → transient pressure, use exponential backoff
        if (response.status === 429 && retryOnStatus(response.status)) {
          const retryAfterMs = parseRetryAfterMs(response.headers);
          const retryAfterSeconds =
            retryAfterMs !== null ? retryAfterMs / 1000 : null;

          if (
            retryAfterSeconds !== null &&
            retryAfterSeconds > RETRY_AFTER_STOP_THRESHOLD_SECONDS
          ) {
            // Quota/billing exhaustion — surface immediately, do not retry
            console.log(
              `Return code: 429 with Retry-After: ${retryAfterSeconds}s (exceeds threshold). Not retrying.`
            );
            return response;
          }

          if (
            attempt === maxRetries ||
            Date.now() - startTime > maxRetryTime
          ) {
            return response;
          }

          const delay =
            retryAfterMs !== null
              ? Math.min(retryAfterMs, maxDelay)
              : Math.min(baseDelay * 2 ** attempt, maxDelay);

          console.log(`Return code: 429. Retrying fetch after ${delay}ms`);
          await new Promise(resolve => setTimeout(resolve, delay));
          attempt++;
          continue;
        }

        if (
          response.ok ||
          !retryOnStatus(response.status) ||
          attempt === maxRetries ||
          Date.now() - startTime > maxRetryTime
        ) {
          // Always return the response, even if it's not ok
          return response;
        }

        // Exponential backoff delay
        const delay = Math.min(baseDelay * 2 ** attempt, maxDelay);
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
