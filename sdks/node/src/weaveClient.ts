import {AsyncLocalStorage} from 'async_hooks';
import * as fs from 'fs';
import {uuidv7} from 'uuidv7';

import {
  EVAL_META_KEY,
  EVALUATION_RUN_OP_NAME,
  MAX_OBJECT_NAME_LENGTH,
} from './constants';
import {computeDigest} from './digest';
import {
  type AgentChatMessage as AgentChatMessageSchema,
  type AgentTraceChatRes,
  type AgentSchema,
  type AgentSpanSchema,
  type AgentVersionSchema,
  type CallSchema,
  type CallsQueryReq,
  type CallsFilter,
  type EndedCallSchemaForInsert,
  type Query,
  type SortBy,
  type StartedCallSchemaForInsert,
  type Api as TraceServerApi,
  type HttpResponse,
  type HTTPValidationError,
} from './generated/traceServerApi';
import {
  type AudioType,
  DEFAULT_AUDIO_TYPE,
  DEFAULT_IMAGE_TYPE,
  type ImageType,
  isWeaveAudio,
  isWeaveImage,
} from './media';
import {
  type Op,
  OpRef,
  type ParameterNamesOption,
  getOpName,
  getOpWrappedFunction,
  isOp,
} from './opType';
import {makeSettings, type Settings} from './settings';
import {Table, TableRef, TableRowRef} from './table';
import {linkAssetToRegistry} from './traceServerBindings/linkAssetToRegistry';
import type {
  LinkAssetToRegistryReq,
  LinkAssetToRegistryRes,
} from './traceServerBindings/linkAssetToRegistry';
import {packageVersion} from './utils/userAgent';
import {ObjectRef, WeaveObject, getClassChain} from './weaveObject';
import {type Call, CallState, InternalCall} from './call';
import {CallRef} from './refs';
import type {Prompt} from './prompt';

const WEAVE_ERRORS_LOG_FNAME = 'weaveErrors.log';
const DEFAULT_GET_CALLS_LIMIT = 1000;

export type Response<T extends unknown> = HttpResponse<T, HTTPValidationError>;

/**
 * Serialized representation of a file blob stored in the Weave content store.
 * Returned by serializedFileBlob/serializedImage/serializedAudio.
 */
interface SerializedFileBlob {
  _type: 'CustomWeaveType';
  weave_type: {type: string};
  files: Record<string, string>;
  load_op: string;
}

/**
 * Shape of a single item in the call batch queue.
 */
type BatchItem =
  | {mode: 'start'; data: {start: CallStartParams}}
  | {mode: 'end'; data: {end: CallEndParams}};

export type CallStackEntry = {
  callId: string;
  traceId: string;
  childSummary: Record<string, any>;
  opName?: string;
  displayName?: string;
};

export interface GetCallsOptions {
  filter?: CallsFilter;
  query?: Query;
  includeCosts?: boolean;
  includeFeedback?: boolean;
  limit?: number;
  offset?: number;
  sortBy?: SortBy[];
  columns?: string[];
  expandColumns?: string[];
}

export type Agent = AgentSchema;
export type AgentMessage = AgentChatMessageSchema;
export type AgentSpan = AgentSpanSchema;
export type AgentTurn = AgentTraceChatRes;
export type AgentVersion = AgentVersionSchema;

/**
 * Options for {@link WeaveClient.getAgents}.
 */
export interface GetAgentsOptions {
  agentName?: string;
  limit?: number;
  offset?: number;
  sortBy?: SortBy[];
}

/**
 * Result shape returned by {@link WeaveClient.getAgents}.
 */
export type GetAgentsResult = {
  agents: Agent[];
  total_count?: number;
};

/**
 * Options for {@link WeaveClient.getAgentVersions}.
 */
export interface GetAgentVersionsOptions {
  agentName: string;
  /**
   * @min 0
   * @max 10000
   * @default 100
   */
  limit?: number;
  /**
   * @min 0
   * @default 0
   */
  offset?: number;
  sortBy?: SortBy[];
}

/**
 * Result shape returned by {@link WeaveClient.getAgentVersions}.
 */
export type GetAgentVersionsResult = {
  versions: AgentVersion[];
  total_count?: number;
};

/**
 * Options for {@link WeaveClient.getAgentSpans}.
 */
export interface GetAgentSpansOptions {
  agentName?: string;
  /**
   * @min 0
   * @max 10000
   * @default 100
   */
  limit?: number;
  /**
   * @min 0
   * @default 0
   */
  offset?: number;
  sortBy?: SortBy[];
}

/**
 * Result shape returned by {@link WeaveClient.getAgentSpans}.
 */
export type GetAgentSpansResult = {
  spans: AgentSpan[];
  total_count?: number;
};

/**
 * Options for {@link WeaveClient.getAgentTurn}.
 */
export interface GetAgentTurnOptions {
  traceId: string;
  includeFeedback?: boolean;
}

/**
 * Result shape returned by {@link WeaveClient.getAgentTurn}.
 */
export type GetAgentTurnResult = AgentTurn;

/**
 * Options for {@link WeaveClient.getAgentTurns}.
 */
export interface GetAgentTurnsOptions {
  conversationId: string;
  /**
   * @min 0
   * @max 50
   * @default 50
   */
  limit?: number;
  /**
   * @min 0
   * @default 0
   */
  offset?: number;
  includeFeedback?: boolean;
}

/**
 * Result shape returned by {@link WeaveClient.getAgentTurns}.
 */
export type GetAgentTurnsResult = {
  conversation_id: string;
  turns?: AgentTurn[];
  total_turns?: number;
  has_more?: boolean;
  limit?: number;
  offset?: number;
  feedback?: Record<string, any>[] | null;
};

/**
 * Distinguishes the object-based getCalls options form from the legacy
 * positional filter CallsFilter form by checking for GetCallsOptions-only keys.
 *
 * @param value The first argument passed to `getCalls` or `getCallsIterator`.
 * @returns `true` when the value matches the object-based `GetCallsOptions` shape.
 */
function maybeIsGetCallsOptions(
  value: CallsFilter | GetCallsOptions
): value is GetCallsOptions {
  if (value == null) return false;
  const getCallsOptionsKeys: (keyof GetCallsOptions)[] = [
    'filter',
    'query',
    'includeCosts',
    'includeFeedback',
    'limit',
    'offset',
    'sortBy',
    'columns',
    'expandColumns',
  ];
  for (const key of getCallsOptionsKeys) {
    if (key in value) {
      return true;
    }
  }
  return false;
}

function generateTraceId(): string {
  return uuidv7();
}

function generateCallId(): string {
  return uuidv7();
}

export type RegistryLinkable = Prompt | ObjectRef | string;

export interface LinkPromptToRegistryOptions {
  targetPath: string;
  aliases?: string[];
}

export class CallStack {
  constructor(private stack: CallStackEntry[] = []) {}

  peek(): CallStackEntry | null {
    return this.stack[this.stack.length - 1] ?? null;
  }

  pushNewCall(): {
    currentCall: CallStackEntry;
    parentCall?: CallStackEntry;
    newStack: CallStack;
  } {
    const parentCall = this.stack[this.stack.length - 1];

    const callId = generateCallId();
    const traceId = parentCall?.traceId ?? generateTraceId();
    const newCall: CallStackEntry = {callId, traceId, childSummary: {}};
    const newStack = new CallStack([...this.stack, newCall]);
    return {currentCall: newCall, parentCall, newStack};
  }

  /**
   * Push a specific call entry onto the stack
   */
  pushCall(entry: CallStackEntry): CallStack {
    return new CallStack([...this.stack, entry]);
  }

  findLastByOpName(opNames: readonly string[]): CallStackEntry | null {
    const opNameSet = new Set(opNames);
    for (let i = this.stack.length - 1; i >= 0; i--) {
      const entry = this.stack[i];
      if (entry.opName && opNameSet.has(entry.opName)) {
        return entry;
      }
    }
    return null;
  }
}

type CallStartParams = StartedCallSchemaForInsert;
type CallEndParams = EndedCallSchemaForInsert;

// We count characters item by item, and try to limit batches to about this size.
const MAX_BATCH_SIZE_CHARS = 10 * 1024 * 1024;
export class WeaveClient {
  private stackContext = new AsyncLocalStorage<CallStack>();
  private attributesContext = new AsyncLocalStorage<Record<string, any>>();
  private callQueue: BatchItem[] = [];
  private batchProcessTimeout: NodeJS.Timeout | null = null;
  private isBatchProcessing: boolean = false;
  private batchProcessingPromises: Set<Promise<void>> = new Set();
  private readonly BATCH_INTERVAL: number = 200;
  private errorCount = 0;
  private readonly MAX_ERRORS = 10;
  public traceServerApi: TraceServerApi<any>;
  public projectId: string;
  public settings: Settings;

  constructor({
    traceServerApi,
    projectId,
    settings = {},
  }: {
    traceServerApi: TraceServerApi<any>;
    projectId: string;
    settings?: Partial<Settings>;
  }) {
    this.traceServerApi = traceServerApi;
    this.projectId = projectId;
    this.settings = makeSettings(settings);
  }

  /**
   * List agents with aggregated stats.
   *
   * @example
   * ```ts
   * const client = await weave.init('entity/project');
   * const resp = await client.getAgents({limit: 20});
   *
   * for (const agent of resp.data.agents) {
   *   console.log(agent.agent_name, agent.total_input_tokens);
   * }
   *
   * console.log(`total count: ${resp.data.total_count}`)
   * ```
   */
  public getAgents(
    options: GetAgentsOptions = {}
  ): Promise<Response<GetAgentsResult>> {
    const params = {
      project_id: this.projectId,
      sort_by: options.sortBy,
      limit: options.limit,
      offset: options.offset,
    };

    if (options.agentName) {
      Object.assign(params, {
        filters: {agent_name: options.agentName},
      });
    }

    return this.traceServerApi.agents.genaiAgentsQueryAgentsQueryPost(params);
  }

  /**
   * List versions for a given agent.
   *
   * @example
   * ```ts
   * const client = await weave.init('entity/project');
   * const resp = await client.getAgentVersions({agentName: 'my-agent', limit: 20});
   *
   * for (const version of resp.data.versions) {
   *   console.log(version.agent_version, version.total_input_tokens);
   * }
   *
   * console.log(`total count: ${resp.data.total_count}`)
   * ```
   */
  public getAgentVersions(
    options: GetAgentVersionsOptions
  ): Promise<Response<GetAgentVersionsResult>> {
    return this.traceServerApi.agents.genaiAgentVersionsQueryAgentsAgentVersionsQueryPost(
      {
        project_id: this.projectId,
        agent_name: options.agentName,
        sort_by: options.sortBy,
        limit: options.limit,
        offset: options.offset,
      }
    );
  }

  /**
   * Query agent spans, optionally filtered by agent name.
   *
   * @example
   * ```ts
   * const client = await weave.init('entity/project');
   * const resp = await client.getAgentSpans({agentName: 'my-agent', limit: 20});
   *
   * for (const span of resp.data.spans) {
   *   console.log(span.span_id, span.span_name, span.input_tokens);
   * }
   *
   * console.log(`total count: ${resp.data.total_count}`)
   * ```
   */
  public async getAgentSpans(
    options: GetAgentSpansOptions
  ): Promise<Response<GetAgentSpansResult>> {
    const params = {
      project_id: this.projectId,
      sort_by: options.sortBy,
      limit: options.limit,
      offset: options.offset,
    };

    if (options.agentName) {
      Object.assign(params, {
        query: {
          $expr: {
            $eq: [{$getField: 'agent_name'}, {$literal: options.agentName}],
          },
        },
      });
    }
    const resp =
      await this.traceServerApi.agents.genaiSpansQueryAgentsSpansQueryPost(
        params
      );

    return {
      ...resp,
      data: {
        ...resp.data,
        spans: resp.data.spans ?? [],
      },
    };
  }

  /**
   * Get data (including messages) for a single turn (by traceId).
   *
   * @example
   * ```ts
   * const client = await weave.init('entity/project');
   * const resp = await client.getAgentTurn({
   *   traceId: '01997b8a-2c89-7c4d-9d0e-2f7e5b9a1b2c',
   *   includeFeedback: true,
   * });
   *
   * console.log(resp.data.root_span_name, resp.data.total_duration_ms);
   *
   * for (const message of resp.data.messages ?? []) {
   *   if (message.user_message) console.log('user:', message.user_message);
   *   if (message.assistant_message) console.log('assistant:', message.assistant_message);
   * }
   * ```
   */
  public getAgentTurn(
    options: GetAgentTurnOptions
  ): Promise<Response<GetAgentTurnResult>> {
    return this.traceServerApi.agents.genaiTracesChatAgentsTracesChatPost({
      project_id: this.projectId,
      trace_id: options.traceId,
      include_feedback: options.includeFeedback,
    });
  }

  /**
   * Get data (including messages) for many turns (by conversationId).
   *
   * @example
   * ```ts
   * const client = await weave.init('entity/project');
   * const resp = await client.getAgentTurns({
   *   conversationId: 'trace_c50312356de3487fa90e381c9399b5b4',
   *   limit: 20,
   *   includeFeedback: true,
   * });
   *
   * for (const turn of resp.data.turns ?? []) {
   *   console.log(turn.trace_id, turn.root_span_name);
   *   for (const message of turn.messages ?? []) {
   *     if (message.user_message) console.log('user:', message.user_message);
   *     if (message.assistant_message) console.log('assistant:', message.assistant_message);
   *   }
   * }
   *
   * console.log(`total turns: ${resp.data.total_turns}, has more: ${resp.data.has_more}`);
   * ```
   */
  public getAgentTurns(
    options: GetAgentTurnsOptions
  ): Promise<Response<GetAgentTurnsResult>> {
    return this.traceServerApi.agents.genaiConversationChatAgentsConversationsChatPost(
      {
        project_id: this.projectId,
        conversation_id: options.conversationId,
        limit: options.limit,
        offset: options.offset,
        include_feedback: options.includeFeedback,
      }
    );
  }

  private scheduleBatchProcessing() {
    if (this.batchProcessTimeout || this.isBatchProcessing) return;
    const promise = new Promise<void>(resolve => {
      this.batchProcessTimeout = setTimeout(
        () => this.processBatch().then(resolve),
        this.BATCH_INTERVAL
      );
    });
    this.batchProcessingPromises.add(promise);
    promise.finally(() => {
      this.batchProcessingPromises.delete(promise);
    });
  }

  public async waitForBatchProcessing() {
    while (this.batchProcessingPromises.size > 0) {
      await Promise.all(this.batchProcessingPromises);
    }
  }

  private async processBatch() {
    if (this.isBatchProcessing || this.callQueue.length === 0) {
      this.batchProcessTimeout = null;
      return;
    }

    this.isBatchProcessing = true;

    const batchToProcess = [];
    let currentBatchSize = 0;

    while (
      this.callQueue.length > 0 &&
      currentBatchSize < MAX_BATCH_SIZE_CHARS
    ) {
      const item = this.callQueue.shift();
      if (item === undefined) {
        throw new Error('Call queue is empty');
      }

      const itemSize = JSON.stringify(item).length;
      if (itemSize > MAX_BATCH_SIZE_CHARS) {
        fs.appendFileSync(
          WEAVE_ERRORS_LOG_FNAME,
          `Item size ${itemSize} exceeds max batch size ${MAX_BATCH_SIZE_CHARS}.  Item: ${JSON.stringify(item)}\n`
        );
      }

      if (currentBatchSize + itemSize <= MAX_BATCH_SIZE_CHARS) {
        batchToProcess.push(item);
        currentBatchSize += itemSize;
      } else {
        // doesn't fit, put it back
        this.callQueue.unshift(item);
        break;
      }
    }

    if (batchToProcess.length === 0) {
      this.batchProcessTimeout = null;
      return;
    }

    this.isBatchProcessing = true;

    const batchReq = {
      batch: batchToProcess.map(item => {
        if (item.mode === 'start') {
          return {mode: 'start' as const, req: item.data};
        }
        return {mode: 'end' as const, req: item.data};
      }),
    };

    try {
      await this.traceServerApi.call.callStartBatchCallUpsertBatchPost(
        batchReq
      );
    } catch (error) {
      console.error('Error processing batch:', error);
      this.errorCount++;
      fs.appendFileSync(
        WEAVE_ERRORS_LOG_FNAME,
        `Error processing batch: ${error}\n`
      );

      // Put failed items back at the front of the queue
      this.callQueue.unshift(...batchToProcess);

      // Exit if we have too many errors
      if (this.errorCount > this.MAX_ERRORS) {
        console.error(`Exceeded max errors: ${this.MAX_ERRORS}; exiting`);
        process.exit(1);
      }
    } finally {
      this.isBatchProcessing = false;
      this.batchProcessTimeout = null;
      if (this.callQueue.length > 0) {
        this.scheduleBatchProcessing();
      }
    }
  }

  public publish(obj: any, objId?: string): Promise<ObjectRef> {
    if (obj.__savedRef) {
      return obj.__savedRef;
    } else if (obj instanceof WeaveObject) {
      return this.saveObject(obj, objId);
    } else if (isOp(obj)) {
      return this.saveOp(obj);
    } else {
      return this.saveArbitrary(obj, objId);
    }
  }

  public async getCall(
    callId: string,
    includeCosts: boolean = false
  ): Promise<Call> {
    const calls = await this.getCalls({
      filter: {call_ids: [callId]},
      includeCosts,
    });
    if (calls.length === 0) {
      throw new Error(`Call not found: ${callId}`);
    }
    return calls[0];
  }

  private reconcileCallArgs(
    options: GetCallsOptions | CallsFilter,
    includeCosts?: boolean,
    limit?: number
  ): GetCallsOptions {
    let reconciledCallArgs: GetCallsOptions;
    if (maybeIsGetCallsOptions(options)) {
      reconciledCallArgs = options;
    } else {
      reconciledCallArgs = {
        filter: options,
        includeCosts,
        limit,
      };
    }

    return reconciledCallArgs;
  }

  public async getCalls(options?: GetCallsOptions): Promise<Call[]>;
  public async getCalls(
    options?: CallsFilter,
    includeCosts?: boolean,
    limit?: number
  ): Promise<Call[]>;
  public async getCalls(
    options: GetCallsOptions | CallsFilter = {},
    includeCosts?: boolean,
    limit?: number
  ): Promise<Call[]> {
    const callOpts = this.reconcileCallArgs(options, includeCosts, limit);
    const calls: Call[] = [];
    const iterator = this.getCallsIteratorInternal(callOpts);
    for await (const call of iterator) {
      const internalCall = new InternalCall();
      internalCall.updateWithCallSchemaData(call);
      calls.push(internalCall.proxy);
    }
    return calls;
  }

  public getCallsIterator(
    options?: CallsFilter,
    includeCosts?: boolean,
    limit?: number
  ): AsyncIterableIterator<CallSchema>;
  public getCallsIterator(
    options?: GetCallsOptions
  ): AsyncIterableIterator<CallSchema>;
  public getCallsIterator(
    options: GetCallsOptions | CallsFilter = {},
    includeCosts?: boolean,
    limit?: number
  ): AsyncIterableIterator<CallSchema> {
    const callOpts = this.reconcileCallArgs(options, includeCosts, limit);
    return this.getCallsIteratorInternal(callOpts);
  }

  private async *getCallsIteratorInternal(
    options: GetCallsOptions = {}
  ): AsyncIterableIterator<CallSchema> {
    const req: CallsQueryReq = {
      filter: options.filter,
      query: options.query,
      include_costs: options.includeCosts,
      include_feedback: options.includeFeedback,
      limit: options.limit ?? DEFAULT_GET_CALLS_LIMIT,
      offset: options.offset,
      sort_by: options.sortBy,
      columns: options.columns,
      expand_columns: options.expandColumns,
      project_id: this.projectId,
    };

    const resp =
      await this.traceServerApi.calls.callsQueryStreamCallsStreamQueryPost(req);

    const reader = resp.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.trim()) {
          try {
            yield JSON.parse(line);
          } catch (error) {
            console.error('Error parsing JSON:', error, 'Line:', line);
          }
        }
      }
    }

    if (buffer.trim()) {
      try {
        yield JSON.parse(buffer);
      } catch (error) {
        console.error('Error parsing JSON:', error, 'Remaining data:', buffer);
      }
    }
  }

  public async get(ref: ObjectRef): Promise<any> {
    let val: any;
    let dataObj: any;
    try {
      const res = await this.traceServerApi.obj.objReadObjReadPost({
        project_id: ref.projectId,
        object_id: ref.objectId,
        digest: ref.digest,
      });
      dataObj = res.data.obj;
      val = dataObj.val;
    } catch (error) {
      if (error instanceof Error && error.message.includes('404')) {
        throw new Error(`Unable to find object for ref uri: ${ref.uri()}`);
      }
      throw error;
    }

    const t = val?._type;

    if (t == 'StringPrompt') {
      const {StringPrompt} = await import('./prompt');

      const {content, description, name} = val;

      const obj = new StringPrompt({
        name,
        description,
        content,
      });

      obj.__savedRef = ref;

      return obj;
    }

    if (t == 'MessagesPrompt') {
      const {MessagesPrompt} = await import('./prompt');

      const {description, messages, name} = val;

      const obj = new MessagesPrompt({
        name,
        description,
        messages,
      });

      obj.__savedRef = ref;

      return obj;
    }

    if (t == 'Dataset') {
      // Avoid circular dependency
      const {Dataset} = await import('./dataset');

      const {description, rows, name} = val;

      const obj = new Dataset({
        name: name || dataObj.id,
        description,
        rows,
      });

      obj.__savedRef = ref;

      // Load table rows if they are a ref
      await obj.rows.load();

      return obj;
    } else if (t == 'Table') {
      const {rows} = val;
      const obj = new Table(rows);
      obj.__savedRef = ref;

      // Load table rows if they are a ref
      await obj.load();

      return obj;
    } else if (t == 'CustomWeaveType') {
      const typeName = val.weave_type.type;
      if (typeName == 'PIL.Image.Image') {
        const loadedFiles: {[key: string]: Buffer} = {};
        for (const [name, digest] of Object.entries(val.files)) {
          try {
            const fileContent =
              await this.traceServerApi.file.fileContentFileContentPost({
                project_id: this.projectId,
                digest: digest as string,
              });
            loadedFiles[name] = fileContent.data?.content;
          } catch (error) {
            console.error('Error loading file:', error);
          }
        }
        // TODO: Implement getting img back as buffer
        return 'Coming soon!';
      } else if (typeName == 'wave.Wave_read') {
        const loadedFiles: {[key: string]: Buffer} = {};
        for (const [name, digest] of Object.entries(val.files)) {
          try {
            const fileContent =
              await this.traceServerApi.file.fileContentFileContentPost({
                project_id: this.projectId,
                digest: digest as string,
              });
            loadedFiles[name] = fileContent.data?.content;
          } catch (error) {
            console.error('Error loading file:', error);
          }
        }
        // TODO: Implement getting audio back as buffer
        return 'Coming soon!';
      }
    }
    return val;
  }

  private async resolveRegistryPromptRef(
    prompt: RegistryLinkable
  ): Promise<ObjectRef> {
    if (typeof prompt === 'string') {
      return ObjectRef.fromUri(prompt);
    }
    if (prompt instanceof ObjectRef) {
      return prompt;
    }

    const savedRef = prompt.__savedRef;
    if (savedRef == null) {
      throw new Error(
        'linkPromptToRegistry requires a published prompt. Call publish() first or pass an ObjectRef / weave:/// URI.'
      );
    }

    return await savedRef;
  }

  private parseRegistryTargetPath(targetPath: string): {
    registryProject: string;
    portfolioName: string;
  } {
    const match = targetPath.match(/^(wandb-registry-[^/]+)\/([^/]+)$/);
    if (match == null) {
      throw new Error(
        "targetPath must match '<registry_project>/<portfolio_name>' where registry_project starts with 'wandb-registry-'"
      );
    }

    return {
      registryProject: match[1],
      portfolioName: match[2],
    };
  }

  /** Link a published prompt version into a registry portfolio. */
  public async linkPromptToRegistry(
    prompt: RegistryLinkable,
    options: LinkPromptToRegistryOptions
  ): Promise<LinkAssetToRegistryRes> {
    if (!this.projectId.includes('/')) {
      throw new Error(
        "linkPromptToRegistry requires client.projectId in '<entity>/<project>' format"
      );
    }
    const [entityName] = this.projectId.split('/', 1);
    const promptRef = await this.resolveRegistryPromptRef(prompt);
    const {registryProject, portfolioName} = this.parseRegistryTargetPath(
      options.targetPath
    );

    const req: LinkAssetToRegistryReq = {
      ref: promptRef.uri(),
      target: {
        entity_name: entityName,
        project_name: registryProject,
        portfolio_name: portfolioName,
      },
      aliases: [...(options.aliases ?? [])],
    };

    return linkAssetToRegistry(this.traceServerApi, req);
  }

  // save* methods attached __savedRef promises to their values. These must
  // be synchronous, so we can guarantee that calling savedWeaveValues
  // immediately makes __savedRef promises available.

  private saveArbitrary(obj: any, objId?: string): Promise<ObjectRef> {
    if (obj.__savedRef) {
      return obj.__savedRef;
    }

    const ref = (async () => {
      if (!objId) {
        objId = uuidv7();
      }

      const serializedObj = await this.serializedVal(obj);
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: objId,
          val: serializedObj,
        },
      });
      return new ObjectRef(this.projectId, objId, response.data.digest);
    })();

    obj.__savedRef = ref;
    return ref;
  }

  private saveObject(obj: WeaveObject, objId?: string): Promise<ObjectRef> {
    if (obj.__savedRef) {
      return Promise.resolve(obj.__savedRef);
    }
    for (const [_key, value] of Object.entries(obj)) {
      this.saveWeaveValues(value);
    }

    obj.__savedRef = (async () => {
      const classChain = getClassChain(obj);
      const className = classChain[0];
      if (!objId) {
        objId = objectNameToId(obj.name);
      }

      let saveAttrs = obj.saveAttrs();
      saveAttrs = await this.serializedVal(saveAttrs);
      // Frontend does this overly specific check for datasets, so we need to add both _type and _class_name
      // for now.
      //   data._type === 'Dataset' &&
      //   data._class_name === 'Dataset' &&
      //   _.isEqual(data._bases, ['Object', 'BaseModel'])
      const saveValue = {
        _type: className,
        _class_name: className,
        _bases: classChain.slice(1),
        ...saveAttrs,
      };
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: objId,
          val: saveValue,
        },
      });
      const ref = new ObjectRef(this.projectId, objId, response.data.digest);
      return ref;
    })();

    return obj.__savedRef;
  }

  private saveTable(table: Table): void {
    if (table.__savedRef) {
      return;
    }

    table.__savedRef = (async () => {
      const rowsWithoutRefs = table.rows.map(row => {
        return {...row, __savedRef: undefined};
      });
      const rows = await this.serializedVal(rowsWithoutRefs);
      const response =
        await this.traceServerApi.table.tableCreateTableCreatePost({
          table: {
            project_id: this.projectId,
            rows,
          },
        });
      const ref = new TableRef(this.projectId, response.data.digest);
      return ref;
    })();
    const tableQueryPromise = (async () => {
      const tableRef = await table.__savedRef;
      const tableQueryRes =
        await this.traceServerApi.table.tableQueryTableQueryPost({
          project_id: this.projectId,
          digest: tableRef?.digest!,
        });
      return {
        tableDigest: tableRef?.digest!,
        tableQueryResult: tableQueryRes.data,
      };
    })();
    for (let i = 0; i < table.rows.length; i++) {
      const row = table.rows[i];
      row.__savedRef = (async () => {
        const {tableDigest, tableQueryResult} = await tableQueryPromise;
        return new TableRowRef(
          this.projectId,
          tableDigest,
          tableQueryResult.rows[i].digest
        );
      })();
    }
  }

  /**
   * Recursively save a Weave value, attaching __savedRef Promises to
   * nested value that gets its own ref.
   *
   * This function must be synchronous, so that code that does ref-tracking
   * (currently only Dataset/DatasetRow in the js client) has refs
   * available immediately.
   */
  private saveWeaveValues(val: any, visited = new WeakSet()): void {
    if (Array.isArray(val)) {
      val.map(item => this.saveWeaveValues(item, visited));
    } else if (val != null && val.__savedRef) {
      return;
    } else if (val instanceof WeaveObject) {
      this.saveObject(val);
    } else if (val instanceof Table) {
      this.saveTable(val);
    } else if (isWeaveImage(val)) {
      // no-op
    } else if (isWeaveAudio(val)) {
      // no-op
    } else if (isOp(val)) {
      this.saveOp(val);
    } else if (typeof val === 'object' && val !== null) {
      // Detect circular references
      if (visited.has(val)) {
        return;
      }
      visited.add(val);

      for (const [_key, value] of Object.entries(val)) {
        this.saveWeaveValues(value, visited);
      }
    }
  }

  // serialize* methods are async, and return the serialized value
  // of a Weave value.

  private async serializedFileBlob(
    typeName: string,
    fileName: string,
    fileContent: Blob
  ): Promise<SerializedFileBlob> {
    const buffer = await fileContent.arrayBuffer().then(Buffer.from);
    const digest = computeDigest(buffer);

    const placeholder: SerializedFileBlob = {
      _type: 'CustomWeaveType',
      weave_type: {type: typeName},
      files: {
        [fileName]: digest,
      },
      load_op: 'NO_LOAD_OP',
    };

    try {
      await this.traceServerApi.file.fileCreateFileCreatePost({
        project_id: this.projectId,
        // @ts-ignore
        file: fileContent,
      });
    } catch (error) {
      console.error('Error saving file:', error);
    }

    return placeholder;
  }

  private async serializedImage(
    imageData: Buffer,
    imageType: ImageType = DEFAULT_IMAGE_TYPE
  ): Promise<SerializedFileBlob> {
    const blob = new Blob([new Uint8Array(imageData)], {
      type: `image/${imageType}`,
    });
    return this.serializedFileBlob('PIL.Image.Image', 'image.png', blob);
  }

  private async serializedAudio(
    audioData: Buffer,
    audioType: AudioType = DEFAULT_AUDIO_TYPE
  ): Promise<SerializedFileBlob> {
    const blob = new Blob([new Uint8Array(audioData)], {
      type: `audio/${audioType}`,
    });
    return this.serializedFileBlob('wave.Wave_read', 'audio.wav', blob);
  }

  /**
   * Upload raw audio bytes to the Weave content store and return the
   * `CustomWeaveType` placeholder that can be embedded in a call output.
   *
   * Use this when building call outputs manually (e.g. via `saveCallEnd`)
   * where the automatic serialization pipeline from `finishCall` is not used.
   *
   * @param data     Raw audio bytes (WAV for best browser compatibility)
   * @param audioType File format — currently only 'wav' is supported
   */
  public async serializeAudio(
    data: Buffer,
    audioType: AudioType = DEFAULT_AUDIO_TYPE
  ): Promise<SerializedFileBlob> {
    return this.serializedAudio(data, audioType);
  }

  /**
   * Get the serialized value of a Weave value, by recursively
   * resolving any __savedRef promises to their uri().
   *
   * This function is asynchronous, and must be called after saveWeaveValues
   * has been called on the value.
   */
  private async serializedVal(val: any, visited = new WeakSet()): Promise<any> {
    if (Array.isArray(val)) {
      return Promise.all(
        val.map(async item => this.serializedVal(item, visited))
      );
    } else if (val != null && val.__savedRef) {
      return (await val.__savedRef).uri();
    } else if (isWeaveImage(val)) {
      return await this.serializedImage(val.data, val.imageType);
    } else if (isWeaveAudio(val)) {
      return await this.serializedAudio(val.data, val.audioType);
    } else if (val instanceof WeaveObject) {
      throw new Error('Programming error:  WeaveObject not saved');
    } else if (val instanceof Table) {
      throw new Error('Programming error: Table not saved');
    } else if (isOp(val)) {
      throw new Error('Programming error: Op not saved');
    } else if (typeof val === 'object' && val !== null) {
      // Detect circular references
      if (visited.has(val)) {
        return '[Circular]';
      }
      visited.add(val);

      const result: {[key: string]: any} = {};
      for (const [key, value] of Object.entries(val)) {
        result[key] = await this.serializedVal(value, visited);
      }
      return result;
    } else {
      return val;
    }
  }

  public saveCallStart(callStart: CallStartParams) {
    this.callQueue.push({mode: 'start', data: {start: callStart}});
    this.scheduleBatchProcessing();
  }

  public saveCallEnd(callEnd: CallEndParams) {
    this.callQueue.push({mode: 'end', data: {end: callEnd}});
    this.scheduleBatchProcessing();
  }

  public getCallStack(): CallStack {
    return this.stackContext.getStore() || new CallStack();
  }

  public getCurrentAttributes(): Record<string, any> {
    return this.attributesContext.getStore() || {};
  }

  public pushNewCall() {
    return this.getCallStack().pushNewCall();
  }

  public runWithCallStack<T>(callStack: CallStack, fn: () => T): T {
    return this.stackContext.run(callStack, fn);
  }

  public runWithAttributes<T>(attributes: Record<string, any>, fn: () => T): T {
    const mergedAttributes = {
      ...this.getCurrentAttributes(),
      ...attributes,
    };
    return this.attributesContext.run(mergedAttributes, fn);
  }

  private async paramsToCallInputs(
    params: any[],
    thisArg: any,
    parameterNames: ParameterNamesOption
  ) {
    let inputs: Record<string, any> = {};

    // Add 'self' if thisArg is an object (WeaveObject, SDK client, or any other object instance)
    // We exclude primitives, null, undefined, and functions
    if (
      thisArg != null &&
      typeof thisArg === 'object' &&
      !Array.isArray(thisArg)
    ) {
      inputs['self'] = thisArg;
    }
    if (parameterNames === 'useParam0Object') {
      inputs = {...inputs, ...params[0]};
    } else if (parameterNames) {
      params.forEach((arg, index) => {
        inputs[parameterNames[index]] = arg;
      });
    } else {
      params.forEach((arg, index) => {
        inputs[`arg${index}`] = arg;
      });
    }
    this.saveWeaveValues(inputs);
    return await this.serializedVal(inputs);
  }

  public async saveOp(
    op: Op<(...args: any[]) => any>,
    objId?: string
  ): Promise<OpRef> {
    if (op.__savedRef) {
      return op.__savedRef;
    }
    op.__savedRef = (async () => {
      const resolvedObjId = objId || getOpName(op);
      const opFn = getOpWrappedFunction(op);
      const saveValue = await this.serializedFileBlob(
        'Op',
        'obj.py',
        new Blob([opFn.toString()])
      );
      const response = await this.traceServerApi.obj.objCreateObjCreatePost({
        obj: {
          project_id: this.projectId,
          object_id: resolvedObjId,
          val: saveValue,
        },
      });
      const ref = new OpRef(
        this.projectId,
        resolvedObjId,
        response.data.digest
      );

      return ref;
    })();
    return op.__savedRef;
  }

  public async createCall(
    internalCall: InternalCall,
    opRef: OpRef | Op<any>,
    params: any[],
    parameterNames: ParameterNamesOption,
    thisArg: any,
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined,
    startTime: Date,
    displayName?: string,
    attributes?: Record<string, any>
  ) {
    // EvalLinkSpanProcessor runs from OTel callbacks and only has access to
    // the in-memory call stack. Store the short op name for stack lookup
    // because the persisted `opName` below is a full ref URI; store the
    // display name so eval metadata can use the user-facing evaluation name.
    currentCall.opName =
      opRef instanceof OpRef ? opRef.objectId : getOpName(opRef);
    currentCall.displayName = displayName;

    const inputs = await this.paramsToCallInputs(
      params,
      thisArg,
      parameterNames
    );
    if (isOp(opRef)) {
      this.saveOp(opRef);
      opRef = await opRef.__savedRef;
    }

    // Merge custom attributes with default weave attributes
    const combinedAttributes = {
      ...this.settings.attributes,
      ...this.getCurrentAttributes(),
      ...(attributes || {}),
    };
    const mergedAttributes = {
      weave: {
        client_version: packageVersion,
        source: 'js-sdk',
      },
      ...combinedAttributes,
    };

    const startReq = {
      project_id: this.projectId,
      id: currentCall.callId,
      op_name: opRef.uri(),
      trace_id: currentCall.traceId,
      parent_id: parentCall?.callId,
      started_at: startTime.toISOString(),
      display_name: displayName,
      attributes: mergedAttributes,
      inputs,
    };
    internalCall.updateWithCallSchemaData(startReq);
    internalCall.state = CallState.pending;
    return this.saveCallStart(startReq);
  }

  // The eval root is matched by op-name substring (op_name is a ref URI); eval
  // children carry the marker in their attributes.
  private isEvalCall(call: InternalCall): boolean {
    const {attributes, op_name} = call.callSchema;
    return (
      (attributes != null && EVAL_META_KEY in attributes) ||
      (op_name?.includes(EVALUATION_RUN_OP_NAME) ?? false)
    );
  }

  public async finishCall(
    call: InternalCall,
    result: any,
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined,
    summarize: undefined | ((result: any) => Record<string, any>),
    endTime: Date,
    startCallPromise: Promise<void>
  ) {
    // Important to do this first before any awaiting, so we're guaranteed that children
    // summaries are processed before parents!
    const mergedSummary = processSummary(
      result,
      summarize,
      currentCall,
      parentCall
    );
    // ensure end is logged after start is logged
    await startCallPromise;
    this.saveWeaveValues(result);
    result = await this.serializedVal(result);
    const callSchemaExchangeData = {
      ended_at: endTime.toISOString(),
      output: result,
      summary: mergedSummary,
    };
    this.saveCallEnd({
      project_id: this.projectId,
      id: currentCall.callId,
      trace_id: currentCall.traceId,
      is_eval: this.isEvalCall(call),
      ...callSchemaExchangeData,
      // User might change the display name of the call after the call has started.
      // take this into account when logging the end call.
      ...(call.callSchema.display_name === null
        ? null
        : {display_name: call.callSchema.display_name!}),
    });
    call.updateWithCallSchemaData(callSchemaExchangeData);
    call.state = CallState.finished;
  }

  public async finishCallWithException(
    call: InternalCall,
    error: any,
    currentCall: CallStackEntry,
    parentCall: CallStackEntry | undefined,
    endTime: Date,
    startCallPromise: Promise<void>
  ) {
    const mergedSummary = processSummary(
      null,
      undefined,
      currentCall,
      parentCall
    );
    // ensure end is logged after start is logged
    await startCallPromise;
    const callSchemaExchangeData = {
      ended_at: endTime.toISOString(),
      output: null,
      summary: mergedSummary,
      exception: error instanceof Error ? error.message : String(error),
    };
    this.saveCallEnd({
      project_id: this.projectId,
      id: currentCall.callId,
      trace_id: currentCall.traceId,
      is_eval: this.isEvalCall(call),
      ...callSchemaExchangeData,
      // User might change the display name of the call after the call has started.
      // take this into account when logging the end call.
      ...(call.callSchema.display_name === null
        ? null
        : {display_name: call.callSchema.display_name!}),
    });
    call.updateWithCallSchemaData(callSchemaExchangeData);
    call.state = CallState.failed;
  }

  public async updateCall(callId: string, displayName: string) {
    await this.traceServerApi.call.callUpdateCallUpdatePost({
      project_id: this.projectId,
      call_id: callId,
      display_name: displayName,
    });
  }

  /**
   * Add a scorer result (e.g., scorer output) to a call.
   * Used in imperative evaluation to attach scorer results to predict calls.
   *
   * @param predictCallId - ID of the predict call to attach feedback to
   * @param scorerCallId - ID of the scorer call that generated the feedback
   * @param runnableRefUri - URI of the scorer (Op or Object ref)
   * @param scorerOutput - Output of the scorer
   */
  public async addScore(
    predictCallId: string,
    scorerCallId: string,
    runnableRefUri: string,
    scorerOutput: any
  ): Promise<string> {
    // Parse entity and project from projectId (format: "entity/project")
    const [entity, project] = this.projectId.split('/');

    // Build call URIs in weave:/// format
    const predictCallUri = new CallRef(
      entity,
      project,
      predictCallId
    ).toString();
    const scorerCallUri = new CallRef(entity, project, scorerCallId).toString();

    // Extract scorer name from runnable ref URI
    // Format: weave:///{entity}/{project}/op/{op_name}:{digest} or object/{name}:{digest}
    const scorerName =
      runnableRefUri.split('/').pop()?.split(':')[0] || 'unknown';

    // Serialize the scorer output
    this.saveWeaveValues(scorerOutput);
    const serializedOutput = await this.serializedVal(scorerOutput);

    const payload = {
      output: serializedOutput,
    };

    const response =
      await this.traceServerApi.feedback.feedbackCreateFeedbackCreatePost({
        project_id: this.projectId,
        weave_ref: predictCallUri,
        feedback_type: `wandb.runnable.${scorerName}`,
        payload,
        runnable_ref: runnableRefUri,
        call_ref: scorerCallUri,
      });

    return response.data.id;
  }
}

/**
 * Represents a summary object with string keys and any type of values.
 */
type Summary = Record<string, any>;

/**
 * Merges two summary objects, combining their values.
 *
 * @param left - The first summary object to merge.
 * @param right - The second summary object to merge.
 * @returns A new summary object containing the merged values.
 *
 * This function performs a deep merge of two summary objects:
 * - For numeric values, it adds them together.
 * - For nested objects, it recursively merges them.
 * - For other types, the left value "wins".
 */
function mergeSummaries(left: Summary, right: Summary): Summary {
  const result: Summary = {...right};
  for (const [key, leftValue] of Object.entries(left)) {
    if (key in result) {
      if (typeof leftValue === 'number' && typeof result[key] === 'number') {
        result[key] = leftValue + result[key];
      } else if (
        leftValue != null &&
        typeof leftValue === 'object' &&
        result[key] != null &&
        typeof result[key] === 'object'
      ) {
        result[key] = mergeSummaries(leftValue, result[key]);
      } else {
        result[key] = leftValue;
      }
    } else {
      result[key] = leftValue;
    }
  }
  return result;
}

function processSummary(
  result: any,
  summarize: ((result: any) => Record<string, any>) | undefined,
  currentCall: CallStackEntry,
  parentCall: CallStackEntry | undefined
) {
  const ownSummary = summarize && result != null ? summarize(result) : {};

  if (ownSummary.usage) {
    for (const model in ownSummary.usage) {
      if (typeof ownSummary.usage[model] === 'object') {
        ownSummary.usage[model] = {
          requests: 1,
          ...ownSummary.usage[model],
        };
      }
    }
  }

  const mergedSummary = mergeSummaries(ownSummary, currentCall.childSummary);

  if (parentCall) {
    parentCall.childSummary = mergeSummaries(
      mergedSummary,
      parentCall.childSummary
    );
  }

  return mergedSummary;
}

function objectNameToId(name: string): string {
  // Replaces any non-alphanumeric characters with a single dash and removes
  // any leading or trailing dashes. This is more restrictive than the DB
  // constraints and can be relaxed if needed.
  let res = name.replace(/[^\w._]+/g, '-'); // non-words
  res = res.replace(/([._-]{2,})+/g, '-'); // multiple separators
  res = res.replace(/^[-_]+|[-_]+$/g, ''); // leading/trailing separators

  if (!res) {
    throw new Error(`Invalid object name: ${name}`);
  }

  // Truncate if too long
  if (res.length > MAX_OBJECT_NAME_LENGTH) {
    res = res.slice(0, MAX_OBJECT_NAME_LENGTH);
  }

  return res;
}
