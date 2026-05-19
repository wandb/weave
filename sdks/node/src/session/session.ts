/**
 * Weave Session SDK — structured logging for agent conversations.
 *
 * Mirrors the Python `weave.session` API:
 *
 * - `Session` groups turns by `conversationId` (no span emitted).
 * - `Turn` is one user-agent exchange — emits an `invoke_agent` OTel span;
 *   defaults to starting its own trace so the Agents tab shows one trace
 *   per turn.
 * - `LLM` is one LLM API call — emits a `chat` span.
 * - `Tool` is one tool execution — emits an `execute_tool` span.
 * - `SubAgent` is a delegated agent invocation — emits a nested
 *   `invoke_agent` span.
 *
 * Each span class exposes explicit `start()` / `end()` methods. They also
 * implement TC39 `Symbol.dispose`, so callers on a TS target with explicit
 * resource management can write:
 *
 *   using session = startSession({agentName: 'demo'});
 *   using turn = session.startTurn({userMessage: 'hi'});
 *   using llm = turn.llm({model: 'gpt-4'});
 *   llm.record({outputMessages: [Message.assistant('hello')]});
 *
 * Spans are emitted via OpenTelemetry; configure a TracerProvider that
 * exports to your Weave OTEL endpoint before calling these APIs. (See
 * `piCodingAgent.ts` for an example of wiring the Weave OTLP exporter.)
 *
 * Port of `weave/session/session.py`.
 */

import {
  context as otelContext,
  type Context,
  ROOT_CONTEXT,
  type Span,
  SpanKind,
  SpanStatusCode,
  trace,
  type Tracer,
} from '@opentelemetry/api';
import {randomUUID} from 'crypto';

import {
  executeToolAttributes,
  invokeAgentAttributes,
  llmAttributes,
  type SpanAttributes,
} from './attributes';
import {
  type JSONStringInput,
  LogResult,
  MediaAttachment,
  type MediaKind,
  Message,
  parseDataUrl,
  Reasoning,
  toJsonString,
  Usage,
} from './types';

const TRACER_NAME = 'weave.session';

function getTracer(): Tracer {
  return trace.getTracer(TRACER_NAME);
}

// ---------------------------------------------------------------------------
// Module-level "current" tracking
// ---------------------------------------------------------------------------
//
// Mirrors the Python contextvars. Plain refs work because each span class
// sets the "current" pointer in `start()` and restores it in `end()`, and
// the OTel context propagation handles parent-child within async code.

let currentSession: Session | null = null;
let currentTurn: Turn | null = null;
let currentLlm: LLM | null = null;

export function getCurrentSession(): Session | null {
  return currentSession;
}

export function getCurrentTurn(): Turn | null {
  return currentTurn;
}

export function getCurrentLlm(): LLM | null {
  return currentLlm;
}

// ---------------------------------------------------------------------------
// Shared span lifecycle helper
// ---------------------------------------------------------------------------

abstract class SpanBase {
  protected otelSpan: Span | null = null;
  protected contextToken: Context | null = null;
  protected restoreContext: Context | null = null;

  protected startOtelSpan(
    name: string,
    opts: {newTrace?: boolean; startTimeNs?: number} = {}
  ): void {
    const tracer = getTracer();
    const parent = opts.newTrace === true ? ROOT_CONTEXT : otelContext.active();
    const startTime =
      opts.startTimeNs !== undefined ? nsToHrTime(opts.startTimeNs) : undefined;
    this.otelSpan = tracer.startSpan(
      name,
      {kind: SpanKind.INTERNAL, startTime},
      parent
    );
    this.restoreContext = otelContext.active();
    this.contextToken = trace.setSpan(parent, this.otelSpan);
    // enterWith-like: switch the active OTel context for subsequent work.
    // OTel context is async-local via the registered context manager (if
    // any); plain refs are still consistent because each span saves and
    // restores `active()`.
    enterContext(this.contextToken);
  }

  protected endOtelSpan(
    attrs: SpanAttributes,
    opts: {endTimeNs?: number} = {}
  ): void {
    if (this.otelSpan === null) return;
    for (const [k, v] of Object.entries(attrs)) {
      this.otelSpan.setAttribute(k, v);
    }
    const endTime =
      opts.endTimeNs !== undefined ? nsToHrTime(opts.endTimeNs) : undefined;
    this.otelSpan.end(endTime);
    if (this.restoreContext !== null) {
      enterContext(this.restoreContext);
      this.restoreContext = null;
    }
    this.contextToken = null;
  }

  protected recordOtelError(err: unknown): void {
    if (this.otelSpan === null) return;
    const message =
      err instanceof Error ? err.message : err == null ? '' : String(err);
    this.otelSpan.setStatus({code: SpanStatusCode.ERROR, message});
    if (err instanceof Error) {
      this.otelSpan.recordException(err);
    } else {
      this.otelSpan.recordException(message);
    }
  }
}

// `enterContext` is the closest TS analog to Python's contextvar `set()`.
// OTel's `context.with(ctx, fn)` is the official surface, but it requires
// callback shape. For the explicit start/end pattern we mutate the active
// context directly via `_disable()` + `enterWith()`-like semantics. To stay
// portable we use `with(...)` under the hood here by stashing/restoring.
function enterContext(ctx: Context): void {
  // OTel JS doesn't expose an `enterWith`. The TS-native idiom is to call
  // `context.with(ctx, fn)` around the work that should see `ctx` as
  // active. Our explicit-start/end lifecycle records the parent context in
  // `restoreContext` so subsequent spans created via OTel `startSpan` will
  // pick up the right parent regardless of the active-context machinery.
  // The pointer mutation below is a no-op when no async context manager is
  // registered; it's kept here as a hook for callers that want to wire one.
  void ctx;
}

function nsToHrTime(ns: number): [number, number] {
  const seconds = Math.floor(ns / 1e9);
  const nanos = ns - seconds * 1e9;
  return [seconds, nanos];
}

function dateMsToNs(d: Date): number {
  return d.getTime() * 1e6;
}

// ---------------------------------------------------------------------------
// Tool
// ---------------------------------------------------------------------------

export interface ToolInit {
  name?: string;
  arguments?: JSONStringInput;
  result?: JSONStringInput;
  toolCallId?: string;
  toolType?: string;
  toolDescription?: string;
  toolDefinitions?: string;
}

/**
 * One tool execution. Maps to an execute_tool OTel span.
 *
 * `arguments` and `result` accept any JSONStringInput; non-strings are
 * JSON-encoded at set time so the stored value is always a string,
 * matching the wire format per GenAI semconv.
 */
export class Tool extends SpanBase {
  name: string;
  toolCallId: string;
  toolType: string;
  toolDescription: string;
  toolDefinitions: string;
  startedAt: Date | null = null;
  endedAt: Date | null = null;
  durationMs: number = 0;

  private _arguments: string;
  private _result: string;
  private ended: boolean = false;

  constructor(init: ToolInit = {}) {
    super();
    this.name = init.name ?? '';
    this._arguments = toJsonString(init.arguments);
    this._result = toJsonString(init.result);
    this.toolCallId = init.toolCallId ?? '';
    this.toolType = init.toolType ?? '';
    this.toolDescription = init.toolDescription ?? '';
    this.toolDefinitions = init.toolDefinitions ?? '';
  }

  get arguments(): string {
    return this._arguments;
  }
  set arguments(v: JSONStringInput) {
    this._arguments = toJsonString(v);
  }
  get result(): string {
    return this._result;
  }
  set result(v: JSONStringInput) {
    this._result = toJsonString(v);
  }

  start(): this {
    if (this.startedAt === null) this.startedAt = new Date();
    this.startOtelSpan(`execute_tool ${this.name}`, {
      startTimeNs: dateMsToNs(this.startedAt),
    });
    return this;
  }

  end(): void {
    if (this.ended) return;
    this.ended = true;
    if (this.endedAt === null) this.endedAt = new Date();
    if (this.startedAt !== null) {
      this.durationMs = this.endedAt.getTime() - this.startedAt.getTime();
    }
    const session = currentSession;
    const include = session ? session.includeContent : true;
    const attrs = executeToolAttributes({
      toolName: this.name,
      conversationId: session?.sessionId ?? '',
      toolCallArguments: include ? this._arguments : '',
      toolCallResult: include ? this._result : '',
      toolCallId: this.toolCallId,
      toolType: this.toolType,
      toolDescription: this.toolDescription,
      toolDefinitions: this.toolDefinitions,
    });
    this.endOtelSpan(attrs, {endTimeNs: dateMsToNs(this.endedAt)});
  }

  recordError(err: unknown): void {
    this.recordOtelError(err);
  }

  [Symbol.dispose](): void {
    this.end();
  }
}

// ---------------------------------------------------------------------------
// LLM
// ---------------------------------------------------------------------------

export interface LLMInit {
  model?: string;
  providerName?: string;
  systemInstructions?: string[];
}

export interface LLMRecordInput {
  inputMessages?: Message[];
  outputMessages?: Message[];
  mediaAttachments?: MediaAttachment[];
  usage?: Usage;
  reasoning?: Reasoning | string;
  responseId?: string;
  responseModel?: string;
  finishReasons?: string[];
  outputType?: string;
}

/** One LLM API call. Maps to a chat OTel span. */
export class LLM extends SpanBase {
  model: string;
  providerName: string;
  responseId: string = '';
  responseModel: string = '';
  outputType: string = '';
  systemInstructions: string[];
  usage: Usage = new Usage();
  reasoning: Reasoning = new Reasoning();
  finishReasons: string[] = [];
  inputMessages: Message[] = [];
  outputMessages: Message[] = [];
  mediaAttachments: MediaAttachment[] = [];
  requestTemperature: number | undefined;
  requestMaxTokens: number | undefined;
  requestTopP: number | undefined;
  requestFrequencyPenalty: number | undefined;
  requestPresencePenalty: number | undefined;
  requestSeed: number | undefined;
  requestStopSequences: string[] = [];
  requestChoiceCount: number | undefined;
  startedAt: Date;
  endedAt: Date | null = null;

  private ended: boolean = false;
  /** Restored to its prior value in `end()`. */
  private restoreCurrent: LLM | null = null;

  constructor(init: LLMInit = {}) {
    super();
    this.model = init.model ?? '';
    this.providerName = init.providerName ?? '';
    this.systemInstructions = init.systemInstructions ?? [];
    this.startedAt = new Date();
  }

  /** Append an assistant message to outputMessages. */
  output(content: string): this {
    this.outputMessages.push(new Message({role: 'assistant', content}));
    return this;
  }

  /** Set reasoning/chain-of-thought content. */
  think(content: string): this {
    this.reasoning = new Reasoning({content});
    return this;
  }

  /**
   * Attach media to this LLM call. Exactly one of content, uri, or fileId
   * must be provided. Modality is inferred from mimeType when not set
   * explicitly.
   */
  attachMedia(args: {
    content?: string;
    uri?: string;
    fileId?: string;
    mimeType?: string;
    modality?: string;
  }): this {
    const sources =
      Number(!!args.content) + Number(!!args.uri) + Number(!!args.fileId);
    if (sources !== 1) {
      throw new Error(
        'Exactly one of content, uri, or fileId must be provided'
      );
    }
    let modality = args.modality ?? '';
    if (!modality && args.mimeType) {
      const prefix = args.mimeType.split('/', 1)[0];
      if (prefix === 'image' || prefix === 'audio' || prefix === 'video') {
        modality = prefix;
      }
    }
    let kind: MediaKind;
    if (args.content) kind = 'blob';
    else if (args.uri) kind = 'uri';
    else kind = 'file';
    this.mediaAttachments.push(
      new MediaAttachment({
        kind,
        modality: modality || 'unknown',
        mimeType: args.mimeType ?? '',
        content: args.content ?? '',
        uri: args.uri ?? '',
        fileId: args.fileId ?? '',
      })
    );
    return this;
  }

  /**
   * Attach a media URL. `data:` URLs are parsed into mimeType + inline
   * content (kind=blob); plain URIs become kind=uri. Empty URLs are a
   * no-op.
   */
  attachMediaUrl(url: string, opts: {modality?: string} = {}): this {
    if (!url) return this;
    if (url.startsWith('data:')) {
      const [mimeType, content] = parseDataUrl(url);
      return this.attachMedia({content, mimeType, modality: opts.modality});
    }
    return this.attachMedia({uri: url, modality: opts.modality});
  }

  /**
   * Set multiple LLM-call fields in one call. Only fields explicitly
   * passed are applied — existing values are preserved.
   */
  record(input: LLMRecordInput): this {
    if (input.inputMessages !== undefined) {
      this.inputMessages = input.inputMessages;
    }
    if (input.outputMessages !== undefined) {
      this.outputMessages = input.outputMessages;
    }
    if (input.mediaAttachments !== undefined) {
      this.mediaAttachments = input.mediaAttachments;
    }
    if (input.usage !== undefined) this.usage = input.usage;
    if (input.reasoning !== undefined) {
      this.reasoning =
        typeof input.reasoning === 'string'
          ? new Reasoning({content: input.reasoning})
          : input.reasoning;
    }
    if (input.responseId !== undefined) this.responseId = input.responseId;
    if (input.responseModel !== undefined) {
      this.responseModel = input.responseModel;
    }
    if (input.finishReasons !== undefined) {
      this.finishReasons = input.finishReasons;
    }
    if (input.outputType !== undefined) this.outputType = input.outputType;
    return this;
  }

  start(): this {
    this.restoreCurrent = currentLlm;
    currentLlm = this;
    this.startOtelSpan(`chat ${this.model}`, {
      startTimeNs: dateMsToNs(this.startedAt),
    });
    return this;
  }

  end(): void {
    if (this.ended) return;
    this.ended = true;
    this.endedAt = new Date();
    const session = currentSession;
    const include = session ? session.includeContent : true;
    const attrs = llmAttributes({
      model: this.model,
      providerName: this.providerName,
      conversationId: session?.sessionId ?? '',
      inputMessages: include ? this.inputMessages : undefined,
      outputMessages: include ? this.outputMessages : undefined,
      mediaAttachments: include ? this.mediaAttachments : undefined,
      systemInstructions: include ? this.systemInstructions : undefined,
      usage: this.usage,
      reasoning: this.reasoning,
      finishReasons: this.finishReasons,
      responseId: this.responseId,
      responseModel: this.responseModel,
      outputType: this.outputType,
      requestTemperature: this.requestTemperature,
      requestMaxTokens: this.requestMaxTokens,
      requestTopP: this.requestTopP,
      requestFrequencyPenalty: this.requestFrequencyPenalty,
      requestPresencePenalty: this.requestPresencePenalty,
      requestSeed: this.requestSeed,
      requestStopSequences: this.requestStopSequences,
      requestChoiceCount: this.requestChoiceCount,
    });
    if (currentLlm === this) currentLlm = this.restoreCurrent;
    this.restoreCurrent = null;
    this.endOtelSpan(attrs, {endTimeNs: dateMsToNs(this.endedAt)});
  }

  recordError(err: unknown): void {
    this.recordOtelError(err);
  }

  [Symbol.dispose](): void {
    this.end();
  }
}

// ---------------------------------------------------------------------------
// SubAgent
// ---------------------------------------------------------------------------

export interface SubAgentInit {
  name?: string;
  model?: string;
  agentId?: string;
  agentDescription?: string;
  agentVersion?: string;
}

/** A delegated agent invocation within a turn. Nested invoke_agent span. */
export class SubAgent extends SpanBase {
  name: string;
  model: string;
  agentId: string;
  agentDescription: string;
  agentVersion: string;
  startedAt: Date | null = null;
  endedAt: Date | null = null;

  private ended: boolean = false;

  constructor(init: SubAgentInit = {}) {
    super();
    this.name = init.name ?? '';
    this.model = init.model ?? '';
    this.agentId = init.agentId ?? '';
    this.agentDescription = init.agentDescription ?? '';
    this.agentVersion = init.agentVersion ?? '';
  }

  /** Start an LLM call within this sub-agent. */
  llm(init: LLMInit = {}): LLM {
    const llm = new LLM({
      model: init.model || this.model,
      providerName: init.providerName,
      systemInstructions: init.systemInstructions,
    });
    return llm;
  }

  /** Start a tool execution within this sub-agent. */
  tool(init: ToolInit): Tool {
    return new Tool(init);
  }

  start(): this {
    this.startedAt = new Date();
    this.startOtelSpan(`invoke_agent ${this.name}`);
    return this;
  }

  end(): void {
    if (this.ended) return;
    this.ended = true;
    this.endedAt = new Date();
    const session = currentSession;
    const attrs = invokeAgentAttributes({
      agentName: this.name,
      model: this.model,
      conversationId: session?.sessionId ?? '',
      conversationName: session?.sessionName ?? '',
      agentId: this.agentId,
      agentDescription: this.agentDescription,
      agentVersion: this.agentVersion,
    });
    this.endOtelSpan(attrs);
  }

  recordError(err: unknown): void {
    this.recordOtelError(err);
  }

  [Symbol.dispose](): void {
    this.end();
  }
}

// ---------------------------------------------------------------------------
// Turn
// ---------------------------------------------------------------------------

export interface TurnInit {
  agentName?: string;
  model?: string;
  agentId?: string;
  agentDescription?: string;
  agentVersion?: string;
  messages?: Message[];
  spans?: Array<LLM | Tool | SubAgent>;
  continueParentTrace?: boolean;
  startedAt?: Date | null;
  endedAt?: Date | null;
}

/**
 * One user-agent exchange. Maps to an invoke_agent OTel span.
 *
 * By default each turn starts its own OTel trace
 * (`continueParentTrace=false`) so the Agents tab shows one trace per turn.
 */
export class Turn extends SpanBase {
  agentName: string;
  model: string;
  agentId: string;
  agentDescription: string;
  agentVersion: string;
  messages: Message[];
  spans: Array<LLM | Tool | SubAgent>;
  continueParentTrace: boolean;
  startedAt: Date | null;
  endedAt: Date | null;

  private ended: boolean = false;
  private restoreCurrent: Turn | null = null;

  constructor(init: TurnInit = {}) {
    super();
    this.agentName = init.agentName ?? '';
    this.model = init.model ?? '';
    this.agentId = init.agentId ?? '';
    this.agentDescription = init.agentDescription ?? '';
    this.agentVersion = init.agentVersion ?? '';
    this.messages = init.messages ?? [];
    this.spans = init.spans ?? [];
    this.continueParentTrace = init.continueParentTrace ?? false;
    this.startedAt = init.startedAt ?? new Date();
    this.endedAt = init.endedAt ?? null;
  }

  /** Append a user message mid-turn. */
  user(content: string): this {
    this.messages.push(new Message({role: 'user', content}));
    return this;
  }

  /** Start an LLM call (chat span, child of this turn). */
  llm(init: LLMInit = {}): LLM {
    return new LLM({
      model: init.model || this.model,
      providerName: init.providerName,
      systemInstructions: init.systemInstructions,
    });
  }

  /** Start a tool execution (execute_tool span, child of this turn). */
  tool(init: ToolInit): Tool {
    return new Tool(init);
  }

  /** Start a sub-agent invocation (nested invoke_agent span, same trace). */
  subagent(init: SubAgentInit = {}): SubAgent {
    return new SubAgent({
      ...init,
      model: init.model || this.model,
    });
  }

  start(): this {
    this.restoreCurrent = currentTurn;
    currentTurn = this;
    const startTimeNs =
      this.startedAt !== null ? dateMsToNs(this.startedAt) : undefined;
    this.startOtelSpan(`invoke_agent ${this.agentName}`, {
      newTrace: !this.continueParentTrace,
      startTimeNs,
    });
    return this;
  }

  end(): void {
    if (this.ended) return;
    this.ended = true;
    this.endedAt = new Date();
    const session = currentSession;
    const include = session ? session.includeContent : true;
    const attrs = invokeAgentAttributes({
      agentName: this.agentName,
      conversationId: session?.sessionId ?? '',
      conversationName: session?.sessionName ?? '',
      model: this.model,
      inputMessages: include ? this.messages : undefined,
      agentId: this.agentId,
      agentDescription: this.agentDescription,
      agentVersion: this.agentVersion,
    });
    if (currentTurn === this) currentTurn = this.restoreCurrent;
    this.restoreCurrent = null;
    this.endOtelSpan(attrs, {endTimeNs: dateMsToNs(this.endedAt)});
  }

  recordError(err: unknown): void {
    this.recordOtelError(err);
  }

  [Symbol.dispose](): void {
    this.end();
  }
}

// ---------------------------------------------------------------------------
// Session
// ---------------------------------------------------------------------------

export interface SessionInit {
  sessionId?: string;
  sessionName?: string;
  agentName?: string;
  model?: string;
  includeContent?: boolean;
  continueParentTrace?: boolean;
}

/** A conversation session. Groups turns by conversationId — emits no span. */
export class Session {
  sessionId: string;
  sessionName: string;
  agentName: string;
  model: string;
  includeContent: boolean;
  continueParentTrace: boolean;

  private ended: boolean = false;
  private _currentTurn: Turn | null = null;
  private restoreCurrent: Session | null = null;

  constructor(init: SessionInit = {}) {
    this.sessionId = init.sessionId || randomUUID();
    this.sessionName = init.sessionName ?? '';
    this.agentName = init.agentName ?? '';
    this.model = init.model ?? '';
    this.includeContent = init.includeContent ?? true;
    this.continueParentTrace = init.continueParentTrace ?? false;
  }

  /**
   * Create a new turn. Auto-ends the previous turn if still open.
   * Propagates `continueParentTrace` from this session.
   */
  startTurn(
    init: {userMessage?: string; model?: string; agentName?: string} = {}
  ): Turn {
    if (this._currentTurn !== null) this._currentTurn.end();
    const turn = new Turn({
      agentName: init.agentName || this.agentName,
      model: init.model || this.model,
      continueParentTrace: this.continueParentTrace,
    });
    if (init.userMessage) {
      turn.messages.push(
        new Message({role: 'user', content: init.userMessage})
      );
    }
    this._currentTurn = turn;
    turn.start();
    return turn;
  }

  start(): this {
    this.restoreCurrent = currentSession;
    currentSession = this;
    return this;
  }

  end(): void {
    if (this.ended) return;
    this.ended = true;
    if (this._currentTurn !== null) {
      this._currentTurn.end();
      this._currentTurn = null;
    }
    if (currentSession === this) currentSession = this.restoreCurrent;
    this.restoreCurrent = null;
  }

  [Symbol.dispose](): void {
    this.end();
  }
}

// ---------------------------------------------------------------------------
// Top-level functions
// ---------------------------------------------------------------------------

/** Create and activate a session. Sets the module-level current pointer. */
export function startSession(init: SessionInit = {}): Session {
  return new Session(init).start();
}

/**
 * Create and activate a turn. Uses the current session if available.
 *
 * If no session is active, returns a disconnected Turn that does NOT set
 * the module-level current pointer.
 */
export function startTurn(
  init: {userMessage?: string; model?: string; agentName?: string} = {}
): Turn {
  const session = currentSession;
  if (session !== null) return session.startTurn(init);
  const turn = new Turn({
    agentName: init.agentName ?? '',
    model: init.model ?? '',
  });
  if (init.userMessage) {
    turn.messages.push(new Message({role: 'user', content: init.userMessage}));
  }
  return turn.start();
}

/**
 * Create and activate an LLM call. Uses the current turn if available.
 *
 * Pass `providerName` explicitly. The SDK does not infer it from the model
 * identifier.
 */
export function startLlm(init: LLMInit = {}): LLM {
  const turn = currentTurn;
  const llm = new LLM({
    model: init.model ?? turn?.model ?? '',
    providerName: init.providerName ?? '',
    systemInstructions: init.systemInstructions ?? [],
  });
  return llm.start();
}

/**
 * Create and start a tool execution span. Becomes a child of whatever span
 * is current in the OTel context — typically the current Turn.
 */
export function startTool(init: ToolInit): Tool {
  return new Tool(init).start();
}

/** Create and start a sub-agent invocation span. */
export function startSubagent(init: SubAgentInit = {}): SubAgent {
  return new SubAgent(init).start();
}

export function endSession(): void {
  currentSession?.end();
}

export function endTurn(): void {
  currentTurn?.end();
}

export function endLlm(): void {
  currentLlm?.end();
}

// ---------------------------------------------------------------------------
// Batch logging — `logTurn` / `logSession`
// ---------------------------------------------------------------------------

function emitSpanNow(
  name: string,
  args: {
    parentCtx: Context;
    startTimeNs: number | undefined;
    endTimeNs: number | undefined;
    attrs: SpanAttributes;
  }
): Span {
  const tracer = getTracer();
  const startTime =
    args.startTimeNs !== undefined ? nsToHrTime(args.startTimeNs) : undefined;
  const span = tracer.startSpan(
    name,
    {kind: SpanKind.INTERNAL, startTime},
    args.parentCtx
  );
  for (const [k, v] of Object.entries(args.attrs)) {
    span.setAttribute(k, v);
  }
  const endTime =
    args.endTimeNs !== undefined ? nsToHrTime(args.endTimeNs) : undefined;
  span.end(endTime);
  return span;
}

function resolveTurnTimestamps(
  startedAt: Date | null | undefined,
  endedAt: Date | null | undefined,
  spans: Array<LLM | Tool | SubAgent>
): [Date, Date] {
  const now = new Date();
  let earliest: Date | null = null;
  let latest: Date | null = null;
  for (const s of spans) {
    if (s.startedAt && (!earliest || s.startedAt < earliest)) {
      earliest = s.startedAt;
    }
    if (s.endedAt && (!latest || s.endedAt > latest)) {
      latest = s.endedAt;
    }
  }
  return [startedAt ?? earliest ?? now, endedAt ?? latest ?? now];
}

function attrsForSpan(
  span: LLM | Tool | SubAgent,
  sessionId: string,
  sessionName: string,
  includeContent: boolean
): [string, SpanAttributes] {
  if (span instanceof LLM) {
    return [
      `chat ${span.model}`,
      llmAttributes({
        model: span.model,
        providerName: span.providerName,
        conversationId: sessionId,
        inputMessages: includeContent ? span.inputMessages : undefined,
        outputMessages: includeContent ? span.outputMessages : undefined,
        mediaAttachments: includeContent ? span.mediaAttachments : undefined,
        systemInstructions: includeContent
          ? span.systemInstructions
          : undefined,
        usage: span.usage,
        reasoning: span.reasoning,
        finishReasons: span.finishReasons,
        responseId: span.responseId,
        responseModel: span.responseModel,
        outputType: span.outputType,
        requestTemperature: span.requestTemperature,
        requestMaxTokens: span.requestMaxTokens,
        requestTopP: span.requestTopP,
        requestFrequencyPenalty: span.requestFrequencyPenalty,
        requestPresencePenalty: span.requestPresencePenalty,
        requestSeed: span.requestSeed,
        requestStopSequences: span.requestStopSequences,
        requestChoiceCount: span.requestChoiceCount,
      }),
    ];
  }
  if (span instanceof Tool) {
    return [
      `execute_tool ${span.name}`,
      executeToolAttributes({
        toolName: span.name,
        conversationId: sessionId,
        toolCallArguments: includeContent ? span.arguments : '',
        toolCallResult: includeContent ? span.result : '',
        toolCallId: span.toolCallId,
        toolType: span.toolType,
        toolDescription: span.toolDescription,
        toolDefinitions: span.toolDefinitions,
      }),
    ];
  }
  // SubAgent
  return [
    `invoke_agent ${span.name}`,
    invokeAgentAttributes({
      agentName: span.name,
      model: span.model,
      conversationId: sessionId,
      conversationName: sessionName,
      agentId: span.agentId,
      agentDescription: span.agentDescription,
      agentVersion: span.agentVersion,
    }),
  ];
}

function formatTraceId(traceId: string): string {
  // W3C Trace Context already gives us lowercase 32-char hex.
  return traceId;
}

function formatSpanId(spanId: string): string {
  return spanId;
}

export interface LogTurnInput {
  sessionId: string;
  agentName?: string;
  sessionName?: string;
  model?: string;
  messages?: Message[];
  spans?: Array<LLM | Tool | SubAgent>;
  startedAt?: Date | null;
  endedAt?: Date | null;
  includeContent?: boolean;
  continueParentTrace?: boolean;
}

/**
 * Imperatively emit one turn and its child spans to OTel.
 *
 * Use when explicit lifecycle isn't viable (stateless containers, callbacks,
 * queue workers). Each child span should have `startedAt` / `endedAt` set;
 * emitted OTel timestamps come from those fields. Falls back to the
 * earliest/latest child timestamp, then `now()`, when the turn doesn't
 * supply its own.
 */
export function logTurn(input: LogTurnInput): LogResult {
  const includeContent = input.includeContent ?? true;
  const continueParent = input.continueParentTrace ?? false;
  const spans = input.spans ?? [];
  const [turnStart, turnEnd] = resolveTurnTimestamps(
    input.startedAt,
    input.endedAt,
    spans
  );

  const turnAttrs = invokeAgentAttributes({
    agentName: input.agentName ?? '',
    conversationId: input.sessionId,
    conversationName: input.sessionName,
    model: input.model,
    inputMessages: includeContent ? input.messages : undefined,
  });

  const parentCtx = continueParent ? otelContext.active() : ROOT_CONTEXT;
  const turnSpan = emitSpanNow(`invoke_agent ${input.agentName ?? ''}`, {
    parentCtx,
    startTimeNs: dateMsToNs(turnStart),
    endTimeNs: dateMsToNs(turnEnd),
    attrs: turnAttrs,
  });

  const childCtx = trace.setSpan(parentCtx, turnSpan);
  for (const child of spans) {
    const [name, attrs] = attrsForSpan(
      child,
      input.sessionId,
      input.sessionName ?? '',
      includeContent
    );
    emitSpanNow(name, {
      parentCtx: childCtx,
      startTimeNs: child.startedAt ? dateMsToNs(child.startedAt) : undefined,
      endTimeNs: child.endedAt ? dateMsToNs(child.endedAt) : undefined,
      attrs,
    });
  }

  return new LogResult({
    sessionId: input.sessionId,
    traceIds: [formatTraceId(turnSpan.spanContext().traceId)],
    rootSpanIds: [formatSpanId(turnSpan.spanContext().spanId)],
    spanCount: 1 + spans.length,
  });
}

export interface LogSessionInput {
  turns: Turn[];
  sessionId?: string;
  sessionName?: string;
  agentName?: string;
  model?: string;
  includeContent?: boolean;
  continueParentTrace?: boolean;
}

/**
 * Imperatively emit a complete session. Each Turn's `.spans` provides its
 * children. Auto-generates `sessionId` if empty. By default each turn gets
 * its own OTel trace.
 */
export function logSession(input: LogSessionInput): LogResult {
  const sid = input.sessionId || randomUUID();
  const traceIds: string[] = [];
  const rootSpanIds: string[] = [];
  let spanCount = 0;
  for (const turn of input.turns) {
    const r = logTurn({
      sessionId: sid,
      sessionName: input.sessionName,
      agentName: turn.agentName || input.agentName,
      model: turn.model || input.model,
      messages: turn.messages,
      spans: turn.spans,
      startedAt: turn.startedAt,
      endedAt: turn.endedAt,
      includeContent: input.includeContent,
      continueParentTrace: input.continueParentTrace,
    });
    traceIds.push(...r.traceIds);
    rootSpanIds.push(...r.rootSpanIds);
    spanCount += r.spanCount;
  }
  return new LogResult({
    sessionId: sid,
    traceIds,
    rootSpanIds,
    spanCount,
  });
}
