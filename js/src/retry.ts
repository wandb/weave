type RetryOptions = {
  maxRetries?: number;
  baseDelay?: number;
  maxDelay?: number;
  maxRetryTime?: number;
  retryOnStatus?: (status: number) => boolean;
};

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
