/**
 * Sentry Utilities
 *
 * This file provides utility functions for reporting errors to Sentry,
 * a platform for monitoring and tracking errors in real-time.
 * These utilities help streamline the process of capturing and
 * sending error information to Sentry for better debugging and
 * error management in the application.
 *
 * Note: These functions rely on the Sentry configuration of the main application.
 * The Sentry setup and initialization should be handled in the main application,
 * not in this submodule. See frontends/app/src/integrations.ts for the Sentry setup.
 *
 */

import * as Sentry from '@sentry/react';

export const sentryDedupeSuffix = '[sentry:dedupe]';

/**
 * Options for capturing errors in Sentry.
 *
 * @property tags - An optional object containing custom tags for Sentry.
 * @property fingerprint - An optional array of strings used to group similar events in Sentry.
 */
type SentryOptions = {
  tags?: Record<string, string>;
  fingerprint?: string[];
};

/**
 * Captures an error in Sentry and logs it to the console with a dedupe suffix.
 *
 * @param error - The error to be captured and logged. Can be a string or an Error object.
 * @param options - Optional. An object containing custom tags and fingerprint for Sentry.
 */
export function captureAndLogError(
  error: string | Error,
  options?: SentryOptions
): void {
  const {tags, fingerprint} = options || {};

  // Capture the error in Sentry with custom tags and fingerprint
  Sentry.captureException(error, {
    tags,
    fingerprint,
  });

  // Prepare the error message
  const errorMessage = error instanceof Error ? error.message : error;
  const dedupeMessage = `${errorMessage} ${sentryDedupeSuffix}`;

  // Log the error to the console
  console.error(dedupeMessage);
}

/**
 * Captures an error in Sentry and throws it with a dedupe suffix.
 *
 * @param error - The error to be captured and thrown. Can be a string or an Error object.
 * @param options - Optional. An object containing custom tags and fingerprint for Sentry.
 * @throws {Error} The original error with a dedupe suffix appended to its message.
 */
export function captureAndThrowError(
  error: string | Error,
  options?: SentryOptions
): never {
  const {tags, fingerprint} = options || {};

  // Capture the error in Sentry with custom tags and fingerprint
  Sentry.captureException(error, {
    tags,
    fingerprint,
  });

  // Prepare the error message
  const errorMessage = error instanceof Error ? error.message : error;
  const dedupeMessage = `${errorMessage} ${sentryDedupeSuffix}`;

  // Throw the error with the dedupe suffix
  if (error instanceof Error) {
    error.message = dedupeMessage;
    throw error;
  } else {
    throw new Error(dedupeMessage);
  }
}
