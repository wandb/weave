/* eslint-disable */
/* tslint:disable */
/*
 * ---------------------------------------------------------------
 * ## THIS FILE WAS GENERATED VIA SWAGGER-TYPESCRIPT-API        ##
 * ##                                                           ##
 * ## AUTHOR: acacode                                           ##
 * ## SOURCE: https://github.com/acacode/swagger-typescript-api ##
 * ---------------------------------------------------------------
 */

/** AndOperation */
export interface AndOperation {
  /** $And */
  $and: (
    | LiteralOperation
    | GetFieldOperator
    | ConvertOperation
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation
  )[];
}

/** Body_file_create_file_create_post */
export interface BodyFileCreateFileCreatePost {
  /** Project Id */
  project_id: string;
  /**
   * File
   * @format binary
   */
  file: File;
}

/** CallBatchEndMode */
export interface CallBatchEndMode {
  /**
   * Mode
   * @default "end"
   */
  mode?: string;
  req: CallEndReq;
}

/** CallBatchStartMode */
export interface CallBatchStartMode {
  /**
   * Mode
   * @default "start"
   */
  mode?: string;
  req: CallStartReq;
}

/** CallCreateBatchReq */
export interface CallCreateBatchReq {
  /** Batch */
  batch: (CallBatchStartMode | CallBatchEndMode)[];
}

/** CallCreateBatchRes */
export interface CallCreateBatchRes {
  /** Res */
  res: (CallStartRes | CallEndRes)[];
}

/** CallEndReq */
export interface CallEndReq {
  end: EndedCallSchemaForInsert;
}

/** CallEndRes */
export type CallEndRes = object;

/** CallReadReq */
export interface CallReadReq {
  /** Project Id */
  project_id: string;
  /** Id */
  id: string;
  /**
   * Include Costs
   * @default false
   */
  include_costs?: boolean | null;
}

/** CallReadRes */
export interface CallReadRes {
  call: CallSchema | null;
}

/** CallSchema */
export interface CallSchema {
  /** Id */
  id: string;
  /** Project Id */
  project_id: string;
  /** Op Name */
  op_name: string;
  /** Display Name */
  display_name?: string | null;
  /** Trace Id */
  trace_id: string;
  /** Parent Id */
  parent_id?: string | null;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
  /** Attributes */
  attributes: object;
  /** Inputs */
  inputs: object;
  /** Ended At */
  ended_at?: string | null;
  /** Exception */
  exception?: string | null;
  /** Output */
  output?: null;
  summary?: object;
  /** Wb User Id */
  wb_user_id?: string | null;
  /** Wb Run Id */
  wb_run_id?: string | null;
  /** Deleted At */
  deleted_at?: string | null;
}

/** CallStartReq */
export interface CallStartReq {
  start: StartedCallSchemaForInsert;
}

/** CallStartRes */
export interface CallStartRes {
  /** Id */
  id: string;
  /** Trace Id */
  trace_id: string;
}

/** CallUpdateReq */
export interface CallUpdateReq {
  /** Project Id */
  project_id: string;
  /** Call Id */
  call_id: string;
  /** Display Name */
  display_name?: string | null;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** CallUpdateRes */
export type CallUpdateRes = object;

/** CallsDeleteReq */
export interface CallsDeleteReq {
  /** Project Id */
  project_id: string;
  /** Call Ids */
  call_ids: string[];
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** CallsDeleteRes */
export type CallsDeleteRes = object;

/** CallsFilter */
export interface CallsFilter {
  /** Op Names */
  op_names?: string[] | null;
  /** Input Refs */
  input_refs?: string[] | null;
  /** Output Refs */
  output_refs?: string[] | null;
  /** Parent Ids */
  parent_ids?: string[] | null;
  /** Trace Ids */
  trace_ids?: string[] | null;
  /** Call Ids */
  call_ids?: string[] | null;
  /** Trace Roots Only */
  trace_roots_only?: boolean | null;
  /** Wb User Ids */
  wb_user_ids?: string[] | null;
  /** Wb Run Ids */
  wb_run_ids?: string[] | null;
}

/** CallsQueryReq */
export interface CallsQueryReq {
  /** Project Id */
  project_id: string;
  filter?: CallsFilter | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
  /** Sort By */
  sort_by?: SortBy[] | null;
  query?: Query | null;
  /**
   * Include Costs
   * @default false
   */
  include_costs?: boolean | null;
  /** Columns */
  columns?: string[] | null;
  /**
   * Expand Columns
   * Columns to expand, i.e. refs to other objects
   */
  expand_columns?: string[] | null;
}

/** CallsQueryStatsReq */
export interface CallsQueryStatsReq {
  /** Project Id */
  project_id: string;
  filter?: CallsFilter | null;
  query?: Query | null;
}

/** CallsQueryStatsRes */
export interface CallsQueryStatsRes {
  /** Count */
  count: number;
}

/** ContainsOperation */
export interface ContainsOperation {
  $contains: ContainsSpec;
}

/** ContainsSpec */
export interface ContainsSpec {
  /** Input */
  input:
    | LiteralOperation
    | GetFieldOperator
    | ConvertOperation
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation;
  /** Substr */
  substr:
    | LiteralOperation
    | GetFieldOperator
    | ConvertOperation
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation;
  /**
   * Case Insensitive
   * @default false
   */
  case_insensitive?: boolean | null;
}

/** ConvertOperation */
export interface ConvertOperation {
  $convert: ConvertSpec;
}

/** ConvertSpec */
export interface ConvertSpec {
  /** Input */
  input:
    | LiteralOperation
    | GetFieldOperator
    | ConvertOperation
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation;
  /** To */
  to: 'double' | 'string' | 'int' | 'bool' | 'exists';
}

/** EndedCallSchemaForInsert */
export interface EndedCallSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Id */
  id: string;
  /**
   * Ended At
   * @format date-time
   */
  ended_at: string;
  /** Exception */
  exception?: string | null;
  /** Output */
  output?: null;
  summary: SummaryInsertMap;
}

/** EqOperation */
export interface EqOperation {
  /**
   * $Eq
   * @maxItems 2
   * @minItems 2
   */
  $eq: any[];
}

/** FeedbackCreateReq */
export interface FeedbackCreateReq {
  /** Project Id */
  project_id: string;
  /** Weave Ref */
  weave_ref: string;
  /** Creator */
  creator?: string | null;
  /** Feedback Type */
  feedback_type: string;
  /** Payload */
  payload: object;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
}

/** FeedbackCreateRes */
export interface FeedbackCreateRes {
  /** Id */
  id: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Wb User Id */
  wb_user_id: string;
  /** Payload */
  payload: object;
}

/** FeedbackPurgeReq */
export interface FeedbackPurgeReq {
  /** Project Id */
  project_id: string;
  query: Query;
}

/** FeedbackPurgeRes */
export type FeedbackPurgeRes = object;

/** FeedbackQueryReq */
export interface FeedbackQueryReq {
  /** Project Id */
  project_id: string;
  /** Fields */
  fields?: string[] | null;
  query?: Query | null;
  /** Sort By */
  sort_by?: SortBy[] | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
}

/** FeedbackQueryRes */
export interface FeedbackQueryRes {
  /** Result */
  result: object[];
}

/** FileContentReadReq */
export interface FileContentReadReq {
  /** Project Id */
  project_id: string;
  /** Digest */
  digest: string;
}

/** FileCreateRes */
export interface FileCreateRes {
  /** Digest */
  digest: string;
}

/** GetFieldOperator */
export interface GetFieldOperator {
  /** $Getfield */
  $getField: string;
}

/** GtOperation */
export interface GtOperation {
  /**
   * $Gt
   * @maxItems 2
   * @minItems 2
   */
  $gt: any[];
}

/** GteOperation */
export interface GteOperation {
  /**
   * $Gte
   * @maxItems 2
   * @minItems 2
   */
  $gte: any[];
}

/** HTTPValidationError */
export interface HTTPValidationError {
  /** Detail */
  detail?: ValidationError[];
}

/** InOperation */
export interface InOperation {
  /**
   * $In
   * @maxItems 2
   * @minItems 2
   */
  $in: any[];
}

/** LLMUsageSchema */
export interface LLMUsageSchema {
  /** Prompt Tokens */
  prompt_tokens?: number | null;
  /** Input Tokens */
  input_tokens?: number | null;
  /** Completion Tokens */
  completion_tokens?: number | null;
  /** Output Tokens */
  output_tokens?: number | null;
  /** Requests */
  requests?: number | null;
  /** Total Tokens */
  total_tokens?: number | null;
}

/** LiteralOperation */
export interface LiteralOperation {
  /** $Literal */
  $literal:
    | string
    | number
    | boolean
    | Record<string, LiteralOperation>
    | LiteralOperation[]
    | null;
}

/** NotOperation */
export interface NotOperation {
  /**
   * $Not
   * @maxItems 1
   * @minItems 1
   */
  $not: any[];
}

/** ObjCreateReq */
export interface ObjCreateReq {
  obj: ObjSchemaForInsert;
}

/** ObjCreateRes */
export interface ObjCreateRes {
  /** Digest */
  digest: string;
}

/** ObjQueryReq */
export interface ObjQueryReq {
  /** Project Id */
  project_id: string;
  filter?: ObjectVersionFilter | null;
}

/** ObjQueryRes */
export interface ObjQueryRes {
  /** Objs */
  objs: ObjSchema[];
}

/** ObjReadReq */
export interface ObjReadReq {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /** Digest */
  digest: string;
}

/** ObjReadRes */
export interface ObjReadRes {
  obj: ObjSchema;
}

/** ObjSchema */
export interface ObjSchema {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /**
   * Created At
   * @format date-time
   */
  created_at: string;
  /** Deleted At */
  deleted_at?: string | null;
  /** Digest */
  digest: string;
  /** Version Index */
  version_index: number;
  /** Is Latest */
  is_latest: number;
  /** Kind */
  kind: string;
  /** Base Object Class */
  base_object_class: string | null;
  /** Val */
  val: any;
}

/** ObjSchemaForInsert */
export interface ObjSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Object Id */
  object_id: string;
  /** Val */
  val: any;
}

/** ObjectVersionFilter */
export interface ObjectVersionFilter {
  /** Base Object Classes */
  base_object_classes?: string[] | null;
  /** Object Ids */
  object_ids?: string[] | null;
  /** Is Op */
  is_op?: boolean | null;
  /** Latest Only */
  latest_only?: boolean | null;
}

/** OrOperation */
export interface OrOperation {
  /** $Or */
  $or: (
    | LiteralOperation
    | GetFieldOperator
    | ConvertOperation
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation
  )[];
}

/** Query */
export interface Query {
  /** $Expr */
  $expr:
    | AndOperation
    | OrOperation
    | NotOperation
    | EqOperation
    | GtOperation
    | GteOperation
    | InOperation
    | ContainsOperation;
}

/** RefsReadBatchReq */
export interface RefsReadBatchReq {
  /** Refs */
  refs: string[];
}

/** RefsReadBatchRes */
export interface RefsReadBatchRes {
  /** Vals */
  vals: any[];
}

/** ServerInfoRes */
export interface ServerInfoRes {
  /** Min Required Weave Python Version */
  min_required_weave_python_version: string;
}

/** SortBy */
export interface SortBy {
  /** Field */
  field: string;
  /** Direction */
  direction: 'asc' | 'desc';
}

/** StartedCallSchemaForInsert */
export interface StartedCallSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Id */
  id?: string | null;
  /** Op Name */
  op_name: string;
  /** Display Name */
  display_name?: string | null;
  /** Trace Id */
  trace_id?: string | null;
  /** Parent Id */
  parent_id?: string | null;
  /**
   * Started At
   * @format date-time
   */
  started_at: string;
  /** Attributes */
  attributes: object;
  /** Inputs */
  inputs: object;
  /**
   * Wb User Id
   * Do not set directly. Server will automatically populate this field.
   */
  wb_user_id?: string | null;
  /** Wb Run Id */
  wb_run_id?: string | null;
}

/** SummaryInsertMap */
export interface SummaryInsertMap {
  /** Usage */
  usage?: Record<string, LLMUsageSchema>;
  [key: string]: any;
}

/** TableAppendSpec */
export interface TableAppendSpec {
  append: TableAppendSpecPayload;
}

/** TableAppendSpecPayload */
export interface TableAppendSpecPayload {
  /** Row */
  row: object;
}

/** TableCreateReq */
export interface TableCreateReq {
  table: TableSchemaForInsert;
}

/** TableCreateRes */
export interface TableCreateRes {
  /** Digest */
  digest: string;
}

/** TableInsertSpec */
export interface TableInsertSpec {
  insert: TableInsertSpecPayload;
}

/** TableInsertSpecPayload */
export interface TableInsertSpecPayload {
  /** Index */
  index: number;
  /** Row */
  row: object;
}

/** TablePopSpec */
export interface TablePopSpec {
  pop: TablePopSpecPayload;
}

/** TablePopSpecPayload */
export interface TablePopSpecPayload {
  /** Index */
  index: number;
}

/** TableQueryReq */
export interface TableQueryReq {
  /** Project Id */
  project_id: string;
  /** Digest */
  digest: string;
  filter?: TableRowFilter | null;
  /** Limit */
  limit?: number | null;
  /** Offset */
  offset?: number | null;
}

/** TableQueryRes */
export interface TableQueryRes {
  /** Rows */
  rows: TableRowSchema[];
}

/** TableRowFilter */
export interface TableRowFilter {
  /** Row Digests */
  row_digests?: string[] | null;
}

/** TableRowSchema */
export interface TableRowSchema {
  /** Digest */
  digest: string;
  /** Val */
  val: any;
}

/** TableSchemaForInsert */
export interface TableSchemaForInsert {
  /** Project Id */
  project_id: string;
  /** Rows */
  rows: object[];
}

/** TableUpdateReq */
export interface TableUpdateReq {
  /** Project Id */
  project_id: string;
  /** Base Digest */
  base_digest: string;
  /** Updates */
  updates: (TableAppendSpec | TablePopSpec | TableInsertSpec)[];
}

/** TableUpdateRes */
export interface TableUpdateRes {
  /** Digest */
  digest: string;
}

/** ValidationError */
export interface ValidationError {
  /** Location */
  loc: (string | number)[];
  /** Message */
  msg: string;
  /** Error Type */
  type: string;
}

export type QueryParamsType = Record<string | number, any>;
export type ResponseFormat = keyof Omit<Body, 'body' | 'bodyUsed'>;

export interface FullRequestParams extends Omit<RequestInit, 'body'> {
  /** set parameter to `true` for call `securityWorker` for this request */
  secure?: boolean;
  /** request path */
  path: string;
  /** content type of request body */
  type?: ContentType;
  /** query params */
  query?: QueryParamsType;
  /** format of response (i.e. response.json() -> format: "json") */
  format?: ResponseFormat;
  /** request body */
  body?: unknown;
  /** base url */
  baseUrl?: string;
  /** request cancellation token */
  cancelToken?: CancelToken;
}

export type RequestParams = Omit<
  FullRequestParams,
  'body' | 'method' | 'query' | 'path'
>;

export interface ApiConfig<SecurityDataType = unknown> {
  baseUrl?: string;
  baseApiParams?: Omit<RequestParams, 'baseUrl' | 'cancelToken' | 'signal'>;
  securityWorker?: (
    securityData: SecurityDataType | null
  ) => Promise<RequestParams | void> | RequestParams | void;
  customFetch?: typeof fetch;
}

export interface HttpResponse<D extends unknown, E extends unknown = unknown>
  extends Response {
  data: D;
  error: E;
}

type CancelToken = Symbol | string | number;

export enum ContentType {
  Json = 'application/json',
  FormData = 'multipart/form-data',
  UrlEncoded = 'application/x-www-form-urlencoded',
  Text = 'text/plain',
}

export class HttpClient<SecurityDataType = unknown> {
  public baseUrl: string = '';
  private securityData: SecurityDataType | null = null;
  private securityWorker?: ApiConfig<SecurityDataType>['securityWorker'];
  private abortControllers = new Map<CancelToken, AbortController>();
  private customFetch = (...fetchParams: Parameters<typeof fetch>) =>
    fetch(...fetchParams);

  private baseApiParams: RequestParams = {
    credentials: 'same-origin',
    headers: {},
    redirect: 'follow',
    referrerPolicy: 'no-referrer',
  };

  constructor(apiConfig: ApiConfig<SecurityDataType> = {}) {
    Object.assign(this, apiConfig);
  }

  public setSecurityData = (data: SecurityDataType | null) => {
    this.securityData = data;
  };

  protected encodeQueryParam(key: string, value: any) {
    const encodedKey = encodeURIComponent(key);
    return `${encodedKey}=${encodeURIComponent(typeof value === 'number' ? value : `${value}`)}`;
  }

  protected addQueryParam(query: QueryParamsType, key: string) {
    return this.encodeQueryParam(key, query[key]);
  }

  protected addArrayQueryParam(query: QueryParamsType, key: string) {
    const value = query[key];
    return value.map((v: any) => this.encodeQueryParam(key, v)).join('&');
  }

  protected toQueryString(rawQuery?: QueryParamsType): string {
    const query = rawQuery || {};
    const keys = Object.keys(query).filter(
      key => 'undefined' !== typeof query[key]
    );
    return keys
      .map(key =>
        Array.isArray(query[key])
          ? this.addArrayQueryParam(query, key)
          : this.addQueryParam(query, key)
      )
      .join('&');
  }

  protected addQueryParams(rawQuery?: QueryParamsType): string {
    const queryString = this.toQueryString(rawQuery);
    return queryString ? `?${queryString}` : '';
  }

  private contentFormatters: Record<ContentType, (input: any) => any> = {
    [ContentType.Json]: (input: any) =>
      input !== null && (typeof input === 'object' || typeof input === 'string')
        ? JSON.stringify(input)
        : input,
    [ContentType.Text]: (input: any) =>
      input !== null && typeof input !== 'string'
        ? JSON.stringify(input)
        : input,
    [ContentType.FormData]: (input: any) =>
      Object.keys(input || {}).reduce((formData, key) => {
        const property = input[key];
        formData.append(
          key,
          property instanceof Blob
            ? property
            : typeof property === 'object' && property !== null
              ? JSON.stringify(property)
              : `${property}`
        );
        return formData;
      }, new FormData()),
    [ContentType.UrlEncoded]: (input: any) => this.toQueryString(input),
  };

  protected mergeRequestParams(
    params1: RequestParams,
    params2?: RequestParams
  ): RequestParams {
    return {
      ...this.baseApiParams,
      ...params1,
      ...(params2 || {}),
      headers: {
        ...(this.baseApiParams.headers || {}),
        ...(params1.headers || {}),
        ...((params2 && params2.headers) || {}),
      },
    };
  }

  protected createAbortSignal = (
    cancelToken: CancelToken
  ): AbortSignal | undefined => {
    if (this.abortControllers.has(cancelToken)) {
      const abortController = this.abortControllers.get(cancelToken);
      if (abortController) {
        return abortController.signal;
      }
      return void 0;
    }

    const abortController = new AbortController();
    this.abortControllers.set(cancelToken, abortController);
    return abortController.signal;
  };

  public abortRequest = (cancelToken: CancelToken) => {
    const abortController = this.abortControllers.get(cancelToken);

    if (abortController) {
      abortController.abort();
      this.abortControllers.delete(cancelToken);
    }
  };

  public request = async <T = any, E = any>({
    body,
    secure,
    path,
    type,
    query,
    format,
    baseUrl,
    cancelToken,
    ...params
  }: FullRequestParams): Promise<HttpResponse<T, E>> => {
    const secureParams =
      ((typeof secure === 'boolean' ? secure : this.baseApiParams.secure) &&
        this.securityWorker &&
        (await this.securityWorker(this.securityData))) ||
      {};
    const requestParams = this.mergeRequestParams(params, secureParams);
    const queryString = query && this.toQueryString(query);
    const payloadFormatter = this.contentFormatters[type || ContentType.Json];
    const responseFormat = format || requestParams.format;

    return this.customFetch(
      `${baseUrl || this.baseUrl || ''}${path}${queryString ? `?${queryString}` : ''}`,
      {
        ...requestParams,
        headers: {
          ...(requestParams.headers || {}),
          ...(type && type !== ContentType.FormData
            ? {'Content-Type': type}
            : {}),
        },
        signal:
          (cancelToken
            ? this.createAbortSignal(cancelToken)
            : requestParams.signal) || null,
        body:
          typeof body === 'undefined' || body === null
            ? null
            : payloadFormatter(body),
      }
    ).then(async response => {
      const r = response.clone() as HttpResponse<T, E>;
      r.data = null as unknown as T;
      r.error = null as unknown as E;

      const data = !responseFormat
        ? r
        : await response[responseFormat]()
            .then(data => {
              if (r.ok) {
                r.data = data;
              } else {
                r.error = data;
              }
              return r;
            })
            .catch(e => {
              r.error = e;
              return r;
            });

      if (cancelToken) {
        this.abortControllers.delete(cancelToken);
      }

      if (!response.ok) throw data;
      return data;
    });
  };
}

/**
 * @title FastAPI
 * @version 0.1.0
 */
export class Api<
  SecurityDataType extends unknown,
> extends HttpClient<SecurityDataType> {
  health = {
    /**
     * No description
     *
     * @tags Service
     * @name ReadRootHealthGet
     * @summary Read Root
     * @request GET:/health
     */
    readRootHealthGet: (params: RequestParams = {}) =>
      this.request<any, any>({
        path: `/health`,
        method: 'GET',
        format: 'json',
        ...params,
      }),
  };
  serverInfo = {
    /**
     * No description
     *
     * @tags Service
     * @name ServerInfoServerInfoGet
     * @summary Server Info
     * @request GET:/server_info
     */
    serverInfoServerInfoGet: (params: RequestParams = {}) =>
      this.request<ServerInfoRes, any>({
        path: `/server_info`,
        method: 'GET',
        format: 'json',
        ...params,
      }),
  };
  call = {
    /**
     * No description
     *
     * @tags Calls
     * @name CallStartCallStartPost
     * @summary Call Start
     * @request POST:/call/start
     * @secure
     */
    callStartCallStartPost: (data: CallStartReq, params: RequestParams = {}) =>
      this.request<CallStartRes, HTTPValidationError>({
        path: `/call/start`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallEndCallEndPost
     * @summary Call End
     * @request POST:/call/end
     * @secure
     */
    callEndCallEndPost: (data: CallEndReq, params: RequestParams = {}) =>
      this.request<CallEndRes, HTTPValidationError>({
        path: `/call/end`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallStartBatchCallUpsertBatchPost
     * @summary Call Start Batch
     * @request POST:/call/upsert_batch
     * @secure
     */
    callStartBatchCallUpsertBatchPost: (
      data: CallCreateBatchReq,
      params: RequestParams = {}
    ) =>
      this.request<CallCreateBatchRes, HTTPValidationError>({
        path: `/call/upsert_batch`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallUpdateCallUpdatePost
     * @summary Call Update
     * @request POST:/call/update
     * @secure
     */
    callUpdateCallUpdatePost: (
      data: CallUpdateReq,
      params: RequestParams = {}
    ) =>
      this.request<CallUpdateRes, HTTPValidationError>({
        path: `/call/update`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallReadCallReadPost
     * @summary Call Read
     * @request POST:/call/read
     * @secure
     */
    callReadCallReadPost: (data: CallReadReq, params: RequestParams = {}) =>
      this.request<CallReadRes, HTTPValidationError>({
        path: `/call/read`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  calls = {
    /**
     * No description
     *
     * @tags Calls
     * @name CallsDeleteCallsDeletePost
     * @summary Calls Delete
     * @request POST:/calls/delete
     * @secure
     */
    callsDeleteCallsDeletePost: (
      data: CallsDeleteReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsDeleteRes, HTTPValidationError>({
        path: `/calls/delete`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallsQueryStatsCallsQueryStatsPost
     * @summary Calls Query Stats
     * @request POST:/calls/query_stats
     * @secure
     */
    callsQueryStatsCallsQueryStatsPost: (
      data: CallsQueryStatsReq,
      params: RequestParams = {}
    ) =>
      this.request<CallsQueryStatsRes, HTTPValidationError>({
        path: `/calls/query_stats`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Calls
     * @name CallsQueryStreamCallsStreamQueryPost
     * @summary Calls Query Stream
     * @request POST:/calls/stream_query
     * @secure
     */
    callsQueryStreamCallsStreamQueryPost: (
      data: CallsQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/calls/stream_query`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  obj = {
    /**
     * No description
     *
     * @tags Objects
     * @name ObjCreateObjCreatePost
     * @summary Obj Create
     * @request POST:/obj/create
     * @secure
     */
    objCreateObjCreatePost: (data: ObjCreateReq, params: RequestParams = {}) =>
      this.request<ObjCreateRes, HTTPValidationError>({
        path: `/obj/create`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Objects
     * @name ObjReadObjReadPost
     * @summary Obj Read
     * @request POST:/obj/read
     * @secure
     */
    objReadObjReadPost: (data: ObjReadReq, params: RequestParams = {}) =>
      this.request<ObjReadRes, HTTPValidationError>({
        path: `/obj/read`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  objs = {
    /**
     * No description
     *
     * @tags Objects
     * @name ObjsQueryObjsQueryPost
     * @summary Objs Query
     * @request POST:/objs/query
     * @secure
     */
    objsQueryObjsQueryPost: (data: ObjQueryReq, params: RequestParams = {}) =>
      this.request<ObjQueryRes, HTTPValidationError>({
        path: `/objs/query`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  table = {
    /**
     * No description
     *
     * @tags Tables
     * @name TableCreateTableCreatePost
     * @summary Table Create
     * @request POST:/table/create
     * @secure
     */
    tableCreateTableCreatePost: (
      data: TableCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<TableCreateRes, HTTPValidationError>({
        path: `/table/create`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableUpdateTableUpdatePost
     * @summary Table Update
     * @request POST:/table/update
     * @secure
     */
    tableUpdateTableUpdatePost: (
      data: TableUpdateReq,
      params: RequestParams = {}
    ) =>
      this.request<TableUpdateRes, HTTPValidationError>({
        path: `/table/update`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Tables
     * @name TableQueryTableQueryPost
     * @summary Table Query
     * @request POST:/table/query
     * @secure
     */
    tableQueryTableQueryPost: (
      data: TableQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<TableQueryRes, HTTPValidationError>({
        path: `/table/query`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  refs = {
    /**
     * No description
     *
     * @tags Refs
     * @name RefsReadBatchRefsReadBatchPost
     * @summary Refs Read Batch
     * @request POST:/refs/read_batch
     * @secure
     */
    refsReadBatchRefsReadBatchPost: (
      data: RefsReadBatchReq,
      params: RequestParams = {}
    ) =>
      this.request<RefsReadBatchRes, HTTPValidationError>({
        path: `/refs/read_batch`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  file = {
    /**
     * No description
     *
     * @tags Files
     * @name FileCreateFileCreatePost
     * @summary File Create
     * @request POST:/file/create
     * @secure
     */
    fileCreateFileCreatePost: (
      data: BodyFileCreateFileCreatePost,
      params: RequestParams = {}
    ) =>
      this.request<FileCreateRes, HTTPValidationError>({
        path: `/file/create`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.FormData,
        format: 'json',
        ...params,
      }),

    /**
     * No description
     *
     * @tags Files
     * @name FileContentFileContentPost
     * @summary File Content
     * @request POST:/file/content
     * @secure
     */
    fileContentFileContentPost: (
      data: FileContentReadReq,
      params: RequestParams = {}
    ) =>
      this.request<any, HTTPValidationError>({
        path: `/file/content`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
  feedback = {
    /**
     * @description Add feedback to a call or object.
     *
     * @tags Feedback
     * @name FeedbackCreateFeedbackCreatePost
     * @summary Feedback Create
     * @request POST:/feedback/create
     * @secure
     */
    feedbackCreateFeedbackCreatePost: (
      data: FeedbackCreateReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackCreateRes, HTTPValidationError>({
        path: `/feedback/create`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Query for feedback.
     *
     * @tags Feedback
     * @name FeedbackQueryFeedbackQueryPost
     * @summary Feedback Query
     * @request POST:/feedback/query
     * @secure
     */
    feedbackQueryFeedbackQueryPost: (
      data: FeedbackQueryReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackQueryRes, HTTPValidationError>({
        path: `/feedback/query`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),

    /**
     * @description Permanently delete feedback.
     *
     * @tags Feedback
     * @name FeedbackPurgeFeedbackPurgePost
     * @summary Feedback Purge
     * @request POST:/feedback/purge
     * @secure
     */
    feedbackPurgeFeedbackPurgePost: (
      data: FeedbackPurgeReq,
      params: RequestParams = {}
    ) =>
      this.request<FeedbackPurgeRes, HTTPValidationError>({
        path: `/feedback/purge`,
        method: 'POST',
        body: data,
        secure: true,
        type: ContentType.Json,
        format: 'json',
        ...params,
      }),
  };
}
