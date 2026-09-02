// File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

import type { RequestInit, RequestInfo, BodyInit } from './internal/builtin-types';
import type { HTTPMethod, PromiseOrValue, MergedRequestInit, FinalizedRequestInit } from './internal/types';
import { uuid4 } from './internal/utils/uuid';
import { validatePositiveInteger, isAbsoluteURL, safeJSON } from './internal/utils/values';
import { sleep } from './internal/utils/sleep';
export type { Logger, LogLevel } from './internal/utils/log';
import { castToError, isAbortError } from './internal/errors';
import type { APIResponseProps } from './internal/parse';
import { getPlatformHeaders } from './internal/detect-platform';
import * as Shims from './internal/shims';
import * as Opts from './internal/request-options';
import { stringifyQuery } from './internal/utils/query';
import { VERSION } from './version';
import * as Errors from './core/error';
import * as Uploads from './core/uploads';
import * as API from './resources/index';
import { APIPromise } from './core/api-promise';
import {
  CallDeleteParams,
  CallDeleteResponse,
  CallEndParams,
  CallEndResponse,
  CallQueryStatsParams,
  CallQueryStatsResponse,
  CallReadParams,
  CallReadResponse,
  CallScoreParams,
  CallScoreResponse,
  CallStartParams,
  CallStartResponse,
  CallStatsParams,
  CallStatsResponse,
  CallStreamQueryParams,
  CallStreamQueryResponse,
  CallUpdateParams,
  CallUpdateResponse,
  CallUpsertBatchParams,
  CallUpsertBatchResponse,
  CallUsageParams,
  CallUsageResponse,
  Calls,
} from './resources/calls';
import {
  CostCreateParams,
  CostCreateResponse,
  CostPurgeParams,
  CostPurgeResponse,
  CostQueryParams,
  CostQueryResponse,
  Costs,
} from './resources/costs';
import {
  EvaluationEvaluateModelParams,
  EvaluationEvaluateModelResponse,
  EvaluationRescoreParams,
  EvaluationRescoreResponse,
  EvaluationStatusParams,
  EvaluationStatusResponse,
  Evaluations,
} from './resources/evaluations';
import {
  Feedback,
  FeedbackAggregateParams,
  FeedbackAggregateResponse,
  FeedbackBatchCreateParams,
  FeedbackBatchCreateResponse,
  FeedbackCreateParams,
  FeedbackCreateResponse,
  FeedbackPayloadSchemaParams,
  FeedbackPayloadSchemaResponse,
  FeedbackPurgeParams,
  FeedbackPurgeResponse,
  FeedbackQueryParams,
  FeedbackQueryResponse,
  FeedbackReplaceParams,
  FeedbackReplaceResponse,
  FeedbackStatsParams,
  FeedbackStatsResponse,
} from './resources/feedback';
import {
  FileContentParams,
  FileContentResponse,
  FileCreateParams,
  FileCreateResponse,
  FileStatsParams,
  FileStatsResponse,
  Files,
} from './resources/files';
import { ImageCreateParams, ImageCreateResponse, Images } from './resources/images';
import { Otel, OtelExportResponse } from './resources/otel';
import { RefReadBatchParams, RefReadBatchResponse, Refs } from './resources/refs';
import {
  ServerInfoRes,
  ServiceHealthCheckResponse,
  ServiceProjectsInfoParams,
  ServiceProjectsInfoResponse,
  Services,
} from './resources/services';
import {
  TableCreateFromDigestsParams,
  TableCreateFromDigestsResponse,
  TableCreateParams,
  TableCreateResponse,
  TableQueryParams,
  TableQueryResponse,
  TableQueryStatsBatchParams,
  TableQueryStatsBatchResponse,
  TableQueryStatsParams,
  TableQueryStatsResponse,
  TableUpdateParams,
  TableUpdateResponse,
  Tables,
} from './resources/tables';
import { ThreadStreamQueryParams, ThreadStreamQueryResponse, Threads } from './resources/threads';
import { Trace, TraceUsageParams, TraceUsageResponse } from './resources/trace';
import { V2CallCompleteParams, V2CallCompleteResponse, V2Calls } from './resources/v2-calls';
import {
  V2DatasetCreateParams,
  V2DatasetCreateResponse,
  V2DatasetDeleteParams,
  V2DatasetDeleteResponse,
  V2DatasetListParams,
  V2DatasetListResponse,
  V2DatasetReadParams,
  V2DatasetReadResponse,
  V2Datasets,
} from './resources/v2-datasets';
import {
  V2EvalResultQueryParams,
  V2EvalResultQueryResponse,
  V2EvalResults,
} from './resources/v2-eval-results';
import {
  V2EvaluationRunCreateParams,
  V2EvaluationRunCreateResponse,
  V2EvaluationRunDeleteParams,
  V2EvaluationRunDeleteResponse,
  V2EvaluationRunFinishParams,
  V2EvaluationRunFinishResponse,
  V2EvaluationRunListParams,
  V2EvaluationRunListResponse,
  V2EvaluationRunReadParams,
  V2EvaluationRunReadResponse,
  V2EvaluationRuns,
} from './resources/v2-evaluation-runs';
import {
  V2EvaluationCreateParams,
  V2EvaluationCreateResponse,
  V2EvaluationDeleteParams,
  V2EvaluationDeleteResponse,
  V2EvaluationListParams,
  V2EvaluationListResponse,
  V2EvaluationReadParams,
  V2EvaluationReadResponse,
  V2Evaluations,
} from './resources/v2-evaluations';
import {
  V2ModelCreateParams,
  V2ModelCreateResponse,
  V2ModelDeleteParams,
  V2ModelDeleteResponse,
  V2ModelListParams,
  V2ModelListResponse,
  V2ModelReadParams,
  V2ModelReadResponse,
  V2Models,
} from './resources/v2-models';
import {
  V2OpCreateParams,
  V2OpCreateResponse,
  V2OpDeleteParams,
  V2OpDeleteResponse,
  V2OpListParams,
  V2OpListResponse,
  V2OpReadParams,
  V2OpReadResponse,
  V2Ops,
} from './resources/v2-ops';
import {
  V2PredictionCreateParams,
  V2PredictionCreateResponse,
  V2PredictionDeleteParams,
  V2PredictionDeleteResponse,
  V2PredictionFinishParams,
  V2PredictionFinishResponse,
  V2PredictionListParams,
  V2PredictionListResponse,
  V2PredictionReadParams,
  V2PredictionReadResponse,
  V2Predictions,
} from './resources/v2-predictions';
import { V2RuntimeApplyParams, V2RuntimeApplyResponse, V2Runtimes } from './resources/v2-runtimes';
import {
  V2ScorerCreateParams,
  V2ScorerCreateResponse,
  V2ScorerDeleteParams,
  V2ScorerDeleteResponse,
  V2ScorerListParams,
  V2ScorerListResponse,
  V2ScorerReadParams,
  V2ScorerReadResponse,
  V2Scorers,
} from './resources/v2-scorers';
import {
  V2ScoreCreateParams,
  V2ScoreCreateResponse,
  V2ScoreDeleteParams,
  V2ScoreDeleteResponse,
  V2ScoreListParams,
  V2ScoreListResponse,
  V2ScoreReadParams,
  V2ScoreReadResponse,
  V2Scores,
} from './resources/v2-scores';
import {
  AgentQueryParams,
  AgentQueryResponse,
  AgentSearchParams,
  AgentSearchResponse,
  AgentTraceChatRes,
  Agents,
} from './resources/agents/agents';
import {
  AnnotationQueueCreateParams,
  AnnotationQueueCreateResponse,
  AnnotationQueueDeleteParams,
  AnnotationQueueDeleteResponse,
  AnnotationQueueQueryParams,
  AnnotationQueueReadParams,
  AnnotationQueueReadResponse,
  AnnotationQueueSchema,
  AnnotationQueueStatsParams,
  AnnotationQueueStatsResponse,
  AnnotationQueueUpdateParams,
  AnnotationQueueUpdateResponse,
  AnnotationQueues,
} from './resources/annotation-queues/annotation-queues';
import {
  ObjectCreateParams,
  ObjectCreateResponse,
  ObjectDeleteParams,
  ObjectDeleteResponse,
  ObjectQueryParams,
  ObjectQueryResponse,
  ObjectReadParams,
  ObjectReadResponse,
  Objects,
} from './resources/objects/objects';
import { type Fetch } from './internal/builtin-types';
import { HeadersLike, NullableHeaders, buildHeaders } from './internal/headers';
import { FinalRequestOptions, RequestOptions } from './internal/request-options';
import { toBase64 } from './internal/utils/base64';
import { readEnv } from './internal/utils/env';
import {
  type LogLevel,
  type Logger,
  formatRequestDetails,
  loggerFor,
  parseLogLevel,
} from './internal/utils/log';
import { isEmptyObj } from './internal/utils/values';

export interface ClientOptions {
  /**
   * Weights & Biases username
   */
  username?: string | undefined;

  /**
   * Weights & Biases API key
   */
  password?: string | undefined;

  /**
   * Override the default base URL for the API, e.g., "https://api.example.com/v2/"
   *
   * Defaults to process.env['WEAVE_TRACE_BASE_URL'].
   */
  baseURL?: string | null | undefined;

  /**
   * The maximum amount of time (in milliseconds) that the client should wait for a response
   * from the server before timing out a single request.
   *
   * Note that request timeouts are retried by default, so in a worst-case scenario you may wait
   * much longer than this timeout before the promise succeeds or fails.
   *
   * @unit milliseconds
   */
  timeout?: number | undefined;
  /**
   * Additional `RequestInit` options to be passed to `fetch` calls.
   * Properties will be overridden by per-request `fetchOptions`.
   */
  fetchOptions?: MergedRequestInit | undefined;

  /**
   * Specify a custom `fetch` function implementation.
   *
   * If not provided, we expect that `fetch` is defined globally.
   */
  fetch?: Fetch | undefined;

  /**
   * The maximum number of times that the client will retry a request in case of a
   * temporary failure, like a network error or a 5XX error from the server.
   *
   * @default 2
   */
  maxRetries?: number | undefined;

  /**
   * Default headers to include with every request to the API.
   *
   * These can be removed in individual requests by explicitly setting the
   * header to `null` in request options.
   */
  defaultHeaders?: HeadersLike | undefined;

  /**
   * Default query parameters to include with every request to the API.
   *
   * These can be removed in individual requests by explicitly setting the
   * param to `undefined` in request options.
   */
  defaultQuery?: Record<string, string | undefined> | undefined;

  /**
   * Set the log level.
   *
   * Defaults to process.env['WEAVE_TRACE_LOG'] or 'warn' if it isn't set.
   */
  logLevel?: LogLevel | undefined;

  /**
   * Set the logger.
   *
   * Defaults to globalThis.console.
   */
  logger?: Logger | undefined;
}

/**
 * API Client for interfacing with the Weave Trace API.
 */
export class WeaveTrace {
  username: string;
  password: string;

  baseURL: string;
  maxRetries: number;
  timeout: number;
  logger: Logger;
  logLevel: LogLevel | undefined;
  fetchOptions: MergedRequestInit | undefined;

  private fetch: Fetch;
  #encoder: Opts.RequestEncoder;
  protected idempotencyHeader?: string;
  private _options: ClientOptions;

  /**
   * API Client for interfacing with the Weave Trace API.
   *
   * @param {string | undefined} [opts.username=process.env['WANDB_USERNAME'] ?? undefined]
   * @param {string | undefined} [opts.password=process.env['WANDB_API_KEY'] ?? undefined]
   * @param {string} [opts.baseURL=process.env['WEAVE_TRACE_BASE_URL'] ?? https://trace.wandb.ai] - Override the default base URL for the API.
   * @param {number} [opts.timeout=1 minute] - The maximum amount of time (in milliseconds) the client will wait for a response before timing out.
   * @param {MergedRequestInit} [opts.fetchOptions] - Additional `RequestInit` options to be passed to `fetch` calls.
   * @param {Fetch} [opts.fetch] - Specify a custom `fetch` function implementation.
   * @param {number} [opts.maxRetries=2] - The maximum number of times the client will retry a request.
   * @param {HeadersLike} opts.defaultHeaders - Default headers to include with every request to the API.
   * @param {Record<string, string | undefined>} opts.defaultQuery - Default query parameters to include with every request to the API.
   */
  constructor({
    baseURL = readEnv('WEAVE_TRACE_BASE_URL'),
    username = readEnv('WANDB_USERNAME'),
    password = readEnv('WANDB_API_KEY'),
    ...opts
  }: ClientOptions = {}) {
    if (username === undefined) {
      throw new Errors.WeaveTraceError(
        "The WANDB_USERNAME environment variable is missing or empty; either provide it, or instantiate the WeaveTrace client with an username option, like new WeaveTrace({ username: 'My Username' }).",
      );
    }
    if (password === undefined) {
      throw new Errors.WeaveTraceError(
        "The WANDB_API_KEY environment variable is missing or empty; either provide it, or instantiate the WeaveTrace client with an password option, like new WeaveTrace({ password: 'My Password' }).",
      );
    }

    const options: ClientOptions = {
      username,
      password,
      ...opts,
      baseURL: baseURL || `https://trace.wandb.ai`,
    };

    this.baseURL = options.baseURL!;
    this.timeout = options.timeout ?? WeaveTrace.DEFAULT_TIMEOUT /* 1 minute */;
    this.logger = options.logger ?? console;
    const defaultLogLevel = 'warn';
    // Set default logLevel early so that we can log a warning in parseLogLevel.
    this.logLevel = defaultLogLevel;
    this.logLevel =
      parseLogLevel(options.logLevel, 'ClientOptions.logLevel', this) ??
      parseLogLevel(readEnv('WEAVE_TRACE_LOG'), "process.env['WEAVE_TRACE_LOG']", this) ??
      defaultLogLevel;
    this.fetchOptions = options.fetchOptions;
    this.maxRetries = options.maxRetries ?? 2;
    this.fetch = options.fetch ?? Shims.getDefaultFetch();
    this.#encoder = Opts.FallbackEncoder;

    const customHeadersEnv = readEnv('WEAVE_TRACE_CUSTOM_HEADERS');
    if (customHeadersEnv) {
      const parsed: Record<string, string> = {};
      for (const line of customHeadersEnv.split('\n')) {
        const colon = line.indexOf(':');
        if (colon >= 0) {
          parsed[line.substring(0, colon).trim()] = line.substring(colon + 1).trim();
        }
      }
      options.defaultHeaders = { ...parsed, ...options.defaultHeaders };
    }

    this._options = options;

    this.username = username;
    this.password = password;
  }

  /**
   * Create a new client instance re-using the same options given to the current client with optional overriding.
   */
  withOptions(options: Partial<ClientOptions>): this {
    const client = new (this.constructor as any as new (props: ClientOptions) => typeof this)({
      ...this._options,
      baseURL: this.baseURL,
      maxRetries: this.maxRetries,
      timeout: this.timeout,
      logger: this.logger,
      logLevel: this.logLevel,
      fetch: this.fetch,
      fetchOptions: this.fetchOptions,
      username: this.username,
      password: this.password,
      ...options,
    });
    return client;
  }

  /**
   * Check whether the base URL is set to its default.
   */
  #baseURLOverridden(): boolean {
    return this.baseURL !== 'https://trace.wandb.ai';
  }

  protected defaultQuery(): Record<string, string | undefined> | undefined {
    return this._options.defaultQuery;
  }

  protected validateHeaders({ values, nulls }: NullableHeaders) {
    return;
  }

  protected async authHeaders(opts: FinalRequestOptions): Promise<NullableHeaders | undefined> {
    if (!this.username) {
      return undefined;
    }

    if (!this.password) {
      return undefined;
    }

    const credentials = `${this.username}:${this.password}`;
    const Authorization = `Basic ${toBase64(credentials)}`;
    return buildHeaders([{ Authorization }]);
  }

  protected stringifyQuery(query: object | Record<string, unknown>): string {
    return stringifyQuery(query);
  }

  private getUserAgent(): string {
    return `${this.constructor.name}/JS ${VERSION}`;
  }

  protected defaultIdempotencyKey(): string {
    return `stainless-node-retry-${uuid4()}`;
  }

  protected makeStatusError(
    status: number,
    error: Object,
    message: string | undefined,
    headers: Headers,
  ): Errors.APIError {
    return Errors.APIError.generate(status, error, message, headers);
  }

  buildURL(
    path: string,
    query: Record<string, unknown> | null | undefined,
    defaultBaseURL?: string | undefined,
  ): string {
    const baseURL = (!this.#baseURLOverridden() && defaultBaseURL) || this.baseURL;
    const url =
      isAbsoluteURL(path) ?
        new URL(path)
      : new URL(baseURL + (baseURL.endsWith('/') && path.startsWith('/') ? path.slice(1) : path));

    const defaultQuery = this.defaultQuery();
    const pathQuery = Object.fromEntries(url.searchParams);
    if (!isEmptyObj(defaultQuery) || !isEmptyObj(pathQuery)) {
      query = { ...pathQuery, ...defaultQuery, ...query };
    }

    if (typeof query === 'object' && query && !Array.isArray(query)) {
      url.search = this.stringifyQuery(query);
    }

    return url.toString();
  }

  /**
   * Used as a callback for mutating the given `FinalRequestOptions` object.
   */
  protected async prepareOptions(options: FinalRequestOptions): Promise<void> {}

  /**
   * Used as a callback for mutating the given `RequestInit` object.
   *
   * This is useful for cases where you want to add certain headers based off of
   * the request properties, e.g. `method` or `url`.
   */
  protected async prepareRequest(
    request: RequestInit,
    { url, options }: { url: string; options: FinalRequestOptions },
  ): Promise<void> {}

  get<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('get', path, opts);
  }

  post<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('post', path, opts);
  }

  patch<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('patch', path, opts);
  }

  put<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('put', path, opts);
  }

  delete<Rsp>(path: string, opts?: PromiseOrValue<RequestOptions>): APIPromise<Rsp> {
    return this.methodRequest('delete', path, opts);
  }

  private methodRequest<Rsp>(
    method: HTTPMethod,
    path: string,
    opts?: PromiseOrValue<RequestOptions>,
  ): APIPromise<Rsp> {
    return this.request(
      Promise.resolve(opts).then((opts) => {
        return { method, path, ...opts };
      }),
    );
  }

  request<Rsp>(
    options: PromiseOrValue<FinalRequestOptions>,
    remainingRetries: number | null = null,
  ): APIPromise<Rsp> {
    return new APIPromise(this, this.makeRequest(options, remainingRetries, undefined));
  }

  private async makeRequest(
    optionsInput: PromiseOrValue<FinalRequestOptions>,
    retriesRemaining: number | null,
    retryOfRequestLogID: string | undefined,
  ): Promise<APIResponseProps> {
    const options = await optionsInput;
    const maxRetries = options.maxRetries ?? this.maxRetries;
    if (retriesRemaining == null) {
      retriesRemaining = maxRetries;
    }

    await this.prepareOptions(options);

    const { req, url, timeout } = await this.buildRequest(options, {
      retryCount: maxRetries - retriesRemaining,
    });

    await this.prepareRequest(req, { url, options });

    /** Not an API request ID, just for correlating local log entries. */
    const requestLogID = 'log_' + ((Math.random() * (1 << 24)) | 0).toString(16).padStart(6, '0');
    const retryLogStr = retryOfRequestLogID === undefined ? '' : `, retryOf: ${retryOfRequestLogID}`;
    const startTime = Date.now();

    loggerFor(this).debug(
      `[${requestLogID}] sending request`,
      formatRequestDetails({
        retryOfRequestLogID,
        method: options.method,
        url,
        options,
        headers: req.headers,
      }),
    );

    if (options.signal?.aborted) {
      throw new Errors.APIUserAbortError();
    }

    const controller = new AbortController();
    const response = await this.fetchWithTimeout(url, req, timeout, controller).catch(castToError);
    const headersTime = Date.now();

    if (response instanceof globalThis.Error) {
      const retryMessage = `retrying, ${retriesRemaining} attempts remaining`;
      if (options.signal?.aborted) {
        throw new Errors.APIUserAbortError();
      }
      // detect native connection timeout errors
      // deno throws "TypeError: error sending request for url (https://example/): client error (Connect): tcp connect error: Operation timed out (os error 60): Operation timed out (os error 60)"
      // undici throws "TypeError: fetch failed" with cause "ConnectTimeoutError: Connect Timeout Error (attempted address: example:443, timeout: 1ms)"
      // others do not provide enough information to distinguish timeouts from other connection errors
      const isTimeout =
        isAbortError(response) ||
        /timed? ?out/i.test(String(response) + ('cause' in response ? String(response.cause) : ''));
      if (retriesRemaining) {
        loggerFor(this).info(
          `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} - ${retryMessage}`,
        );
        loggerFor(this).debug(
          `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} (${retryMessage})`,
          formatRequestDetails({
            retryOfRequestLogID,
            url,
            durationMs: headersTime - startTime,
            message: response.message,
          }),
        );
        return this.retryRequest(options, retriesRemaining, retryOfRequestLogID ?? requestLogID);
      }
      loggerFor(this).info(
        `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} - error; no more retries left`,
      );
      loggerFor(this).debug(
        `[${requestLogID}] connection ${isTimeout ? 'timed out' : 'failed'} (error; no more retries left)`,
        formatRequestDetails({
          retryOfRequestLogID,
          url,
          durationMs: headersTime - startTime,
          message: response.message,
        }),
      );
      if (isTimeout) {
        throw new Errors.APIConnectionTimeoutError();
      }
      throw new Errors.APIConnectionError({ cause: response });
    }

    const responseInfo = `[${requestLogID}${retryLogStr}] ${req.method} ${url} ${
      response.ok ? 'succeeded' : 'failed'
    } with status ${response.status} in ${headersTime - startTime}ms`;

    if (!response.ok) {
      const shouldRetry = await this.shouldRetry(response);
      if (retriesRemaining && shouldRetry) {
        const retryMessage = `retrying, ${retriesRemaining} attempts remaining`;

        // We don't need the body of this response.
        await Shims.CancelReadableStream(response.body);
        loggerFor(this).info(`${responseInfo} - ${retryMessage}`);
        loggerFor(this).debug(
          `[${requestLogID}] response error (${retryMessage})`,
          formatRequestDetails({
            retryOfRequestLogID,
            url: response.url,
            status: response.status,
            headers: response.headers,
            durationMs: headersTime - startTime,
          }),
        );
        return this.retryRequest(
          options,
          retriesRemaining,
          retryOfRequestLogID ?? requestLogID,
          response.headers,
        );
      }

      const retryMessage = shouldRetry ? `error; no more retries left` : `error; not retryable`;

      loggerFor(this).info(`${responseInfo} - ${retryMessage}`);

      const errText = await response.text().catch((err: any) => castToError(err).message);
      const errJSON = safeJSON(errText) as any;
      const errMessage = errJSON ? undefined : errText;

      loggerFor(this).debug(
        `[${requestLogID}] response error (${retryMessage})`,
        formatRequestDetails({
          retryOfRequestLogID,
          url: response.url,
          status: response.status,
          headers: response.headers,
          message: errMessage,
          durationMs: Date.now() - startTime,
        }),
      );

      const err = this.makeStatusError(response.status, errJSON, errMessage, response.headers);
      throw err;
    }

    loggerFor(this).info(responseInfo);
    loggerFor(this).debug(
      `[${requestLogID}] response start`,
      formatRequestDetails({
        retryOfRequestLogID,
        url: response.url,
        status: response.status,
        headers: response.headers,
        durationMs: headersTime - startTime,
      }),
    );

    return { response, options, controller, requestLogID, retryOfRequestLogID, startTime };
  }

  async fetchWithTimeout(
    url: RequestInfo,
    init: RequestInit | undefined,
    ms: number,
    controller: AbortController,
  ): Promise<Response> {
    const { signal, method, ...options } = init || {};
    const abort = this._makeAbort(controller);
    if (signal) signal.addEventListener('abort', abort, { once: true });

    const timeout = setTimeout(abort, ms);

    const isReadableBody =
      ((globalThis as any).ReadableStream && options.body instanceof (globalThis as any).ReadableStream) ||
      (typeof options.body === 'object' && options.body !== null && Symbol.asyncIterator in options.body);

    const fetchOptions: RequestInit = {
      signal: controller.signal as any,
      ...(isReadableBody ? { duplex: 'half' } : {}),
      method: 'GET',
      ...options,
    };
    if (method) {
      // Custom methods like 'patch' need to be uppercased
      // See https://github.com/nodejs/undici/issues/2294
      fetchOptions.method = method.toUpperCase();
    }

    try {
      // use undefined this binding; fetch errors if bound to something else in browser/cloudflare
      return await this.fetch.call(undefined, url, fetchOptions);
    } finally {
      clearTimeout(timeout);
    }
  }

  private async shouldRetry(response: Response): Promise<boolean> {
    // Note this is not a standard header.
    const shouldRetryHeader = response.headers.get('x-should-retry');

    // If the server explicitly says whether or not to retry, obey.
    if (shouldRetryHeader === 'true') return true;
    if (shouldRetryHeader === 'false') return false;

    // Retry on request timeouts.
    if (response.status === 408) return true;

    // Retry on lock timeouts.
    if (response.status === 409) return true;

    // Retry on rate limits.
    if (response.status === 429) return true;

    // Retry internal errors.
    if (response.status >= 500) return true;

    return false;
  }

  private async retryRequest(
    options: FinalRequestOptions,
    retriesRemaining: number,
    requestLogID: string,
    responseHeaders?: Headers | undefined,
  ): Promise<APIResponseProps> {
    let timeoutMillis: number | undefined;

    // Note the `retry-after-ms` header may not be standard, but is a good idea and we'd like proactive support for it.
    const retryAfterMillisHeader = responseHeaders?.get('retry-after-ms');
    if (retryAfterMillisHeader) {
      const timeoutMs = parseFloat(retryAfterMillisHeader);
      if (!Number.isNaN(timeoutMs)) {
        timeoutMillis = timeoutMs;
      }
    }

    // About the Retry-After header: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Retry-After
    const retryAfterHeader = responseHeaders?.get('retry-after');
    if (retryAfterHeader && !timeoutMillis) {
      const timeoutSeconds = parseFloat(retryAfterHeader);
      if (!Number.isNaN(timeoutSeconds)) {
        timeoutMillis = timeoutSeconds * 1000;
      } else {
        timeoutMillis = Date.parse(retryAfterHeader) - Date.now();
      }
    }

    // If the API asks us to wait a certain amount of time, just do what it
    // says, but otherwise calculate a default
    if (timeoutMillis === undefined) {
      const maxRetries = options.maxRetries ?? this.maxRetries;
      timeoutMillis = this.calculateDefaultRetryTimeoutMillis(retriesRemaining, maxRetries);
    }
    await sleep(timeoutMillis);

    return this.makeRequest(options, retriesRemaining - 1, requestLogID);
  }

  private calculateDefaultRetryTimeoutMillis(retriesRemaining: number, maxRetries: number): number {
    const initialRetryDelay = 0.5;
    const maxRetryDelay = 8.0;

    const numRetries = maxRetries - retriesRemaining;

    // Apply exponential backoff, but not more than the max.
    const sleepSeconds = Math.min(initialRetryDelay * Math.pow(2, numRetries), maxRetryDelay);

    // Apply some jitter, take up to at most 25 percent of the retry time.
    const jitter = 1 - Math.random() * 0.25;

    return sleepSeconds * jitter * 1000;
  }

  async buildRequest(
    inputOptions: FinalRequestOptions,
    { retryCount = 0 }: { retryCount?: number } = {},
  ): Promise<{ req: FinalizedRequestInit; url: string; timeout: number }> {
    const options = { ...inputOptions };
    const { method, path, query, defaultBaseURL } = options;

    const url = this.buildURL(path!, query as Record<string, unknown>, defaultBaseURL);
    if ('timeout' in options) validatePositiveInteger('timeout', options.timeout);
    options.timeout = options.timeout ?? this.timeout;
    const { bodyHeaders, body } = this.buildBody({ options });
    const reqHeaders = await this.buildHeaders({ options: inputOptions, method, bodyHeaders, retryCount });

    const req: FinalizedRequestInit = {
      method,
      headers: reqHeaders,
      ...(options.signal && { signal: options.signal }),
      ...((globalThis as any).ReadableStream &&
        body instanceof (globalThis as any).ReadableStream && { duplex: 'half' }),
      ...(body && { body }),
      ...((this.fetchOptions as any) ?? {}),
      ...((options.fetchOptions as any) ?? {}),
    };

    return { req, url, timeout: options.timeout };
  }

  private async buildHeaders({
    options,
    method,
    bodyHeaders,
    retryCount,
  }: {
    options: FinalRequestOptions;
    method: HTTPMethod;
    bodyHeaders: HeadersLike;
    retryCount: number;
  }): Promise<Headers> {
    let idempotencyHeaders: HeadersLike = {};
    if (this.idempotencyHeader && method !== 'get') {
      if (!options.idempotencyKey) options.idempotencyKey = this.defaultIdempotencyKey();
      idempotencyHeaders[this.idempotencyHeader] = options.idempotencyKey;
    }

    const headers = buildHeaders([
      idempotencyHeaders,
      {
        Accept: 'application/json',
        'User-Agent': this.getUserAgent(),
        'X-Stainless-Retry-Count': String(retryCount),
        ...(options.timeout ? { 'X-Stainless-Timeout': String(Math.trunc(options.timeout / 1000)) } : {}),
        ...getPlatformHeaders(),
      },
      await this.authHeaders(options),
      this._options.defaultHeaders,
      bodyHeaders,
      options.headers,
    ]);

    this.validateHeaders(headers);

    return headers.values;
  }

  private _makeAbort(controller: AbortController) {
    // note: we can't just inline this method inside `fetchWithTimeout()` because then the closure
    //       would capture all request options, and cause a memory leak.
    return () => controller.abort();
  }

  private buildBody({ options: { body, headers: rawHeaders } }: { options: FinalRequestOptions }): {
    bodyHeaders: HeadersLike;
    body: BodyInit | undefined;
  } {
    if (!body) {
      return { bodyHeaders: undefined, body: undefined };
    }
    const headers = buildHeaders([rawHeaders]);
    if (
      // Pass raw type verbatim
      ArrayBuffer.isView(body) ||
      body instanceof ArrayBuffer ||
      body instanceof DataView ||
      (typeof body === 'string' &&
        // Preserve legacy string encoding behavior for now
        headers.values.has('content-type')) ||
      // `Blob` is superset of `File`
      ((globalThis as any).Blob && body instanceof (globalThis as any).Blob) ||
      // `FormData` -> `multipart/form-data`
      body instanceof FormData ||
      // `URLSearchParams` -> `application/x-www-form-urlencoded`
      body instanceof URLSearchParams ||
      // Send chunked stream (each chunk has own `length`)
      ((globalThis as any).ReadableStream && body instanceof (globalThis as any).ReadableStream)
    ) {
      return { bodyHeaders: undefined, body: body as BodyInit };
    } else if (
      typeof body === 'object' &&
      (Symbol.asyncIterator in body ||
        (Symbol.iterator in body && 'next' in body && typeof body.next === 'function'))
    ) {
      return { bodyHeaders: undefined, body: Shims.ReadableStreamFrom(body as AsyncIterable<Uint8Array>) };
    } else if (
      typeof body === 'object' &&
      headers.values.get('content-type') === 'application/x-www-form-urlencoded'
    ) {
      return {
        bodyHeaders: { 'content-type': 'application/x-www-form-urlencoded' },
        body: this.stringifyQuery(body),
      };
    } else {
      return this.#encoder({ body, headers });
    }
  }

  static WeaveTrace = this;
  static DEFAULT_TIMEOUT = 60000; // 1 minute

  static WeaveTraceError = Errors.WeaveTraceError;
  static APIError = Errors.APIError;
  static APIConnectionError = Errors.APIConnectionError;
  static APIConnectionTimeoutError = Errors.APIConnectionTimeoutError;
  static APIUserAbortError = Errors.APIUserAbortError;
  static NotFoundError = Errors.NotFoundError;
  static ConflictError = Errors.ConflictError;
  static RateLimitError = Errors.RateLimitError;
  static BadRequestError = Errors.BadRequestError;
  static AuthenticationError = Errors.AuthenticationError;
  static InternalServerError = Errors.InternalServerError;
  static PermissionDeniedError = Errors.PermissionDeniedError;
  static UnprocessableEntityError = Errors.UnprocessableEntityError;

  static toFile = Uploads.toFile;

  services: API.Services = new API.Services(this);
  calls: API.Calls = new API.Calls(this);
  objects: API.Objects = new API.Objects(this);
  tables: API.Tables = new API.Tables(this);
  refs: API.Refs = new API.Refs(this);
  files: API.Files = new API.Files(this);
  costs: API.Costs = new API.Costs(this);
  feedback: API.Feedback = new API.Feedback(this);
  otel: API.Otel = new API.Otel(this);
  trace: API.Trace = new API.Trace(this);
  threads: API.Threads = new API.Threads(this);
  agents: API.Agents = new API.Agents(this);
  annotationQueues: API.AnnotationQueues = new API.AnnotationQueues(this);
  evaluations: API.Evaluations = new API.Evaluations(this);
  images: API.Images = new API.Images(this);
  v2Ops: API.V2Ops = new API.V2Ops(this);
  v2Scorers: API.V2Scorers = new API.V2Scorers(this);
  v2Datasets: API.V2Datasets = new API.V2Datasets(this);
  v2Evaluations: API.V2Evaluations = new API.V2Evaluations(this);
  v2Models: API.V2Models = new API.V2Models(this);
  v2EvaluationRuns: API.V2EvaluationRuns = new API.V2EvaluationRuns(this);
  v2Predictions: API.V2Predictions = new API.V2Predictions(this);
  v2Scores: API.V2Scores = new API.V2Scores(this);
  v2Calls: API.V2Calls = new API.V2Calls(this);
  v2Runtimes: API.V2Runtimes = new API.V2Runtimes(this);
  v2EvalResults: API.V2EvalResults = new API.V2EvalResults(this);
}

WeaveTrace.Services = Services;
WeaveTrace.Calls = Calls;
WeaveTrace.Objects = Objects;
WeaveTrace.Tables = Tables;
WeaveTrace.Refs = Refs;
WeaveTrace.Files = Files;
WeaveTrace.Costs = Costs;
WeaveTrace.Feedback = Feedback;
WeaveTrace.Otel = Otel;
WeaveTrace.Trace = Trace;
WeaveTrace.Threads = Threads;
WeaveTrace.Agents = Agents;
WeaveTrace.AnnotationQueues = AnnotationQueues;
WeaveTrace.Evaluations = Evaluations;
WeaveTrace.Images = Images;
WeaveTrace.V2Ops = V2Ops;
WeaveTrace.V2Scorers = V2Scorers;
WeaveTrace.V2Datasets = V2Datasets;
WeaveTrace.V2Evaluations = V2Evaluations;
WeaveTrace.V2Models = V2Models;
WeaveTrace.V2EvaluationRuns = V2EvaluationRuns;
WeaveTrace.V2Predictions = V2Predictions;
WeaveTrace.V2Scores = V2Scores;
WeaveTrace.V2Calls = V2Calls;
WeaveTrace.V2Runtimes = V2Runtimes;
WeaveTrace.V2EvalResults = V2EvalResults;

export declare namespace WeaveTrace {
  export type RequestOptions = Opts.RequestOptions;

  export {
    Services as Services,
    type ServerInfoRes as ServerInfoRes,
    type ServiceHealthCheckResponse as ServiceHealthCheckResponse,
    type ServiceProjectsInfoResponse as ServiceProjectsInfoResponse,
    type ServiceProjectsInfoParams as ServiceProjectsInfoParams,
  };

  export {
    Calls as Calls,
    type CallUpdateResponse as CallUpdateResponse,
    type CallDeleteResponse as CallDeleteResponse,
    type CallEndResponse as CallEndResponse,
    type CallQueryStatsResponse as CallQueryStatsResponse,
    type CallReadResponse as CallReadResponse,
    type CallScoreResponse as CallScoreResponse,
    type CallStartResponse as CallStartResponse,
    type CallStatsResponse as CallStatsResponse,
    type CallStreamQueryResponse as CallStreamQueryResponse,
    type CallUpsertBatchResponse as CallUpsertBatchResponse,
    type CallUsageResponse as CallUsageResponse,
    type CallUpdateParams as CallUpdateParams,
    type CallDeleteParams as CallDeleteParams,
    type CallEndParams as CallEndParams,
    type CallQueryStatsParams as CallQueryStatsParams,
    type CallReadParams as CallReadParams,
    type CallScoreParams as CallScoreParams,
    type CallStartParams as CallStartParams,
    type CallStatsParams as CallStatsParams,
    type CallStreamQueryParams as CallStreamQueryParams,
    type CallUpsertBatchParams as CallUpsertBatchParams,
    type CallUsageParams as CallUsageParams,
  };

  export {
    Objects as Objects,
    type ObjectCreateResponse as ObjectCreateResponse,
    type ObjectDeleteResponse as ObjectDeleteResponse,
    type ObjectQueryResponse as ObjectQueryResponse,
    type ObjectReadResponse as ObjectReadResponse,
    type ObjectCreateParams as ObjectCreateParams,
    type ObjectDeleteParams as ObjectDeleteParams,
    type ObjectQueryParams as ObjectQueryParams,
    type ObjectReadParams as ObjectReadParams,
  };

  export {
    Tables as Tables,
    type TableCreateResponse as TableCreateResponse,
    type TableUpdateResponse as TableUpdateResponse,
    type TableCreateFromDigestsResponse as TableCreateFromDigestsResponse,
    type TableQueryResponse as TableQueryResponse,
    type TableQueryStatsResponse as TableQueryStatsResponse,
    type TableQueryStatsBatchResponse as TableQueryStatsBatchResponse,
    type TableCreateParams as TableCreateParams,
    type TableUpdateParams as TableUpdateParams,
    type TableCreateFromDigestsParams as TableCreateFromDigestsParams,
    type TableQueryParams as TableQueryParams,
    type TableQueryStatsParams as TableQueryStatsParams,
    type TableQueryStatsBatchParams as TableQueryStatsBatchParams,
  };

  export {
    Refs as Refs,
    type RefReadBatchResponse as RefReadBatchResponse,
    type RefReadBatchParams as RefReadBatchParams,
  };

  export {
    Files as Files,
    type FileCreateResponse as FileCreateResponse,
    type FileContentResponse as FileContentResponse,
    type FileStatsResponse as FileStatsResponse,
    type FileCreateParams as FileCreateParams,
    type FileContentParams as FileContentParams,
    type FileStatsParams as FileStatsParams,
  };

  export {
    Costs as Costs,
    type CostCreateResponse as CostCreateResponse,
    type CostPurgeResponse as CostPurgeResponse,
    type CostQueryResponse as CostQueryResponse,
    type CostCreateParams as CostCreateParams,
    type CostPurgeParams as CostPurgeParams,
    type CostQueryParams as CostQueryParams,
  };

  export {
    Feedback as Feedback,
    type FeedbackCreateResponse as FeedbackCreateResponse,
    type FeedbackAggregateResponse as FeedbackAggregateResponse,
    type FeedbackBatchCreateResponse as FeedbackBatchCreateResponse,
    type FeedbackPayloadSchemaResponse as FeedbackPayloadSchemaResponse,
    type FeedbackPurgeResponse as FeedbackPurgeResponse,
    type FeedbackQueryResponse as FeedbackQueryResponse,
    type FeedbackReplaceResponse as FeedbackReplaceResponse,
    type FeedbackStatsResponse as FeedbackStatsResponse,
    type FeedbackCreateParams as FeedbackCreateParams,
    type FeedbackAggregateParams as FeedbackAggregateParams,
    type FeedbackBatchCreateParams as FeedbackBatchCreateParams,
    type FeedbackPayloadSchemaParams as FeedbackPayloadSchemaParams,
    type FeedbackPurgeParams as FeedbackPurgeParams,
    type FeedbackQueryParams as FeedbackQueryParams,
    type FeedbackReplaceParams as FeedbackReplaceParams,
    type FeedbackStatsParams as FeedbackStatsParams,
  };

  export { Otel as Otel, type OtelExportResponse as OtelExportResponse };

  export {
    Trace as Trace,
    type TraceUsageResponse as TraceUsageResponse,
    type TraceUsageParams as TraceUsageParams,
  };

  export {
    Threads as Threads,
    type ThreadStreamQueryResponse as ThreadStreamQueryResponse,
    type ThreadStreamQueryParams as ThreadStreamQueryParams,
  };

  export {
    Agents as Agents,
    type AgentTraceChatRes as AgentTraceChatRes,
    type AgentQueryResponse as AgentQueryResponse,
    type AgentSearchResponse as AgentSearchResponse,
    type AgentQueryParams as AgentQueryParams,
    type AgentSearchParams as AgentSearchParams,
  };

  export {
    AnnotationQueues as AnnotationQueues,
    type AnnotationQueueSchema as AnnotationQueueSchema,
    type AnnotationQueueCreateResponse as AnnotationQueueCreateResponse,
    type AnnotationQueueUpdateResponse as AnnotationQueueUpdateResponse,
    type AnnotationQueueDeleteResponse as AnnotationQueueDeleteResponse,
    type AnnotationQueueReadResponse as AnnotationQueueReadResponse,
    type AnnotationQueueStatsResponse as AnnotationQueueStatsResponse,
    type AnnotationQueueCreateParams as AnnotationQueueCreateParams,
    type AnnotationQueueUpdateParams as AnnotationQueueUpdateParams,
    type AnnotationQueueDeleteParams as AnnotationQueueDeleteParams,
    type AnnotationQueueQueryParams as AnnotationQueueQueryParams,
    type AnnotationQueueReadParams as AnnotationQueueReadParams,
    type AnnotationQueueStatsParams as AnnotationQueueStatsParams,
  };

  export {
    Evaluations as Evaluations,
    type EvaluationEvaluateModelResponse as EvaluationEvaluateModelResponse,
    type EvaluationRescoreResponse as EvaluationRescoreResponse,
    type EvaluationStatusResponse as EvaluationStatusResponse,
    type EvaluationEvaluateModelParams as EvaluationEvaluateModelParams,
    type EvaluationRescoreParams as EvaluationRescoreParams,
    type EvaluationStatusParams as EvaluationStatusParams,
  };

  export {
    Images as Images,
    type ImageCreateResponse as ImageCreateResponse,
    type ImageCreateParams as ImageCreateParams,
  };

  export {
    V2Ops as V2Ops,
    type V2OpCreateResponse as V2OpCreateResponse,
    type V2OpListResponse as V2OpListResponse,
    type V2OpDeleteResponse as V2OpDeleteResponse,
    type V2OpReadResponse as V2OpReadResponse,
    type V2OpCreateParams as V2OpCreateParams,
    type V2OpListParams as V2OpListParams,
    type V2OpDeleteParams as V2OpDeleteParams,
    type V2OpReadParams as V2OpReadParams,
  };

  export {
    V2Scorers as V2Scorers,
    type V2ScorerCreateResponse as V2ScorerCreateResponse,
    type V2ScorerListResponse as V2ScorerListResponse,
    type V2ScorerDeleteResponse as V2ScorerDeleteResponse,
    type V2ScorerReadResponse as V2ScorerReadResponse,
    type V2ScorerCreateParams as V2ScorerCreateParams,
    type V2ScorerListParams as V2ScorerListParams,
    type V2ScorerDeleteParams as V2ScorerDeleteParams,
    type V2ScorerReadParams as V2ScorerReadParams,
  };

  export {
    V2Datasets as V2Datasets,
    type V2DatasetCreateResponse as V2DatasetCreateResponse,
    type V2DatasetListResponse as V2DatasetListResponse,
    type V2DatasetDeleteResponse as V2DatasetDeleteResponse,
    type V2DatasetReadResponse as V2DatasetReadResponse,
    type V2DatasetCreateParams as V2DatasetCreateParams,
    type V2DatasetListParams as V2DatasetListParams,
    type V2DatasetDeleteParams as V2DatasetDeleteParams,
    type V2DatasetReadParams as V2DatasetReadParams,
  };

  export {
    V2Evaluations as V2Evaluations,
    type V2EvaluationCreateResponse as V2EvaluationCreateResponse,
    type V2EvaluationListResponse as V2EvaluationListResponse,
    type V2EvaluationDeleteResponse as V2EvaluationDeleteResponse,
    type V2EvaluationReadResponse as V2EvaluationReadResponse,
    type V2EvaluationCreateParams as V2EvaluationCreateParams,
    type V2EvaluationListParams as V2EvaluationListParams,
    type V2EvaluationDeleteParams as V2EvaluationDeleteParams,
    type V2EvaluationReadParams as V2EvaluationReadParams,
  };

  export {
    V2Models as V2Models,
    type V2ModelCreateResponse as V2ModelCreateResponse,
    type V2ModelListResponse as V2ModelListResponse,
    type V2ModelDeleteResponse as V2ModelDeleteResponse,
    type V2ModelReadResponse as V2ModelReadResponse,
    type V2ModelCreateParams as V2ModelCreateParams,
    type V2ModelListParams as V2ModelListParams,
    type V2ModelDeleteParams as V2ModelDeleteParams,
    type V2ModelReadParams as V2ModelReadParams,
  };

  export {
    V2EvaluationRuns as V2EvaluationRuns,
    type V2EvaluationRunCreateResponse as V2EvaluationRunCreateResponse,
    type V2EvaluationRunListResponse as V2EvaluationRunListResponse,
    type V2EvaluationRunDeleteResponse as V2EvaluationRunDeleteResponse,
    type V2EvaluationRunFinishResponse as V2EvaluationRunFinishResponse,
    type V2EvaluationRunReadResponse as V2EvaluationRunReadResponse,
    type V2EvaluationRunCreateParams as V2EvaluationRunCreateParams,
    type V2EvaluationRunListParams as V2EvaluationRunListParams,
    type V2EvaluationRunDeleteParams as V2EvaluationRunDeleteParams,
    type V2EvaluationRunFinishParams as V2EvaluationRunFinishParams,
    type V2EvaluationRunReadParams as V2EvaluationRunReadParams,
  };

  export {
    V2Predictions as V2Predictions,
    type V2PredictionCreateResponse as V2PredictionCreateResponse,
    type V2PredictionListResponse as V2PredictionListResponse,
    type V2PredictionDeleteResponse as V2PredictionDeleteResponse,
    type V2PredictionFinishResponse as V2PredictionFinishResponse,
    type V2PredictionReadResponse as V2PredictionReadResponse,
    type V2PredictionCreateParams as V2PredictionCreateParams,
    type V2PredictionListParams as V2PredictionListParams,
    type V2PredictionDeleteParams as V2PredictionDeleteParams,
    type V2PredictionFinishParams as V2PredictionFinishParams,
    type V2PredictionReadParams as V2PredictionReadParams,
  };

  export {
    V2Scores as V2Scores,
    type V2ScoreCreateResponse as V2ScoreCreateResponse,
    type V2ScoreListResponse as V2ScoreListResponse,
    type V2ScoreDeleteResponse as V2ScoreDeleteResponse,
    type V2ScoreReadResponse as V2ScoreReadResponse,
    type V2ScoreCreateParams as V2ScoreCreateParams,
    type V2ScoreListParams as V2ScoreListParams,
    type V2ScoreDeleteParams as V2ScoreDeleteParams,
    type V2ScoreReadParams as V2ScoreReadParams,
  };

  export {
    V2Calls as V2Calls,
    type V2CallCompleteResponse as V2CallCompleteResponse,
    type V2CallCompleteParams as V2CallCompleteParams,
  };

  export {
    V2Runtimes as V2Runtimes,
    type V2RuntimeApplyResponse as V2RuntimeApplyResponse,
    type V2RuntimeApplyParams as V2RuntimeApplyParams,
  };

  export {
    V2EvalResults as V2EvalResults,
    type V2EvalResultQueryResponse as V2EvalResultQueryResponse,
    type V2EvalResultQueryParams as V2EvalResultQueryParams,
  };

  export type AndOperation = API.AndOperation;
  export type ContainsOperation = API.ContainsOperation;
  export type ContainsSpec = API.ContainsSpec;
  export type ConvertOperation = API.ConvertOperation;
  export type ConvertSpec = API.ConvertSpec;
  export type EqOperation = API.EqOperation;
  export type GetFieldOperator = API.GetFieldOperator;
  export type GtOperation = API.GtOperation;
  export type GteOperation = API.GteOperation;
  export type InOperation = API.InOperation;
  export type LiteralOperation = API.LiteralOperation;
  export type NotOperation = API.NotOperation;
  export type Operation = API.Operation;
  export type OrOperation = API.OrOperation;
}
