// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

export { WeaveTrace as default } from './client';

export { type Uploadable, toFile } from './core/uploads';
export { APIPromise } from './core/api-promise';
export { WeaveTrace, type ClientOptions } from './client';
export {
  WeaveTraceError,
  APIError,
  APIConnectionError,
  APIConnectionTimeoutError,
  APIUserAbortError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  BadRequestError,
  AuthenticationError,
  InternalServerError,
  PermissionDeniedError,
  UnprocessableEntityError,
} from './core/error';
