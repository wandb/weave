/**
 * Utility functions for consistent error handling in the magician library.
 */

/**
 * Check if an error is an abort error (cancellation).
 *
 * @param error The error to check
 * @returns True if the error is an abort error
 */
export const isAbortError = (error: unknown): boolean => {
  return error instanceof Error && error.name === 'AbortError';
};

/**
 * Check if an error should be handled (not an abort error).
 *
 * @param error The error to check
 * @returns True if the error should be handled
 */
export const shouldHandleError = (error: unknown): error is Error => {
  return error instanceof Error && !isAbortError(error);
};

/**
 * Safely handle errors from async operations.
 *
 * @param error The error to handle
 * @param onError Optional callback for handling non-abort errors
 * @param context Optional context for logging
 */
export const handleAsyncError = (
  error: unknown,
  onError?: (error: Error) => void,
  context?: string
): void => {
  if (shouldHandleError(error)) {
    if (context) {
      console.error(`${context}:`, error);
    } else {
      console.error('Operation error:', error);
    }
    onError?.(error);
  }
}; 