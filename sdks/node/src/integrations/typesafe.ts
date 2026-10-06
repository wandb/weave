/**
 * Spans for TypeSafe `systemOne` calls.
 *
 * One call becomes one provider chat span. This integration does not create a
 * Weave Call. Do not enable it together with another TypeSafe instrumentor;
 * pick one.
 *
 * `captureContent: false` on `wrapTypeSafe` drops state, questions, and
 * answers for that client. Otherwise the process reads
 * `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`. A value of `false`,
 * `0`, `no`, or `off` turns content off. When the variable is absent, content
 * is kept. The per-client option wins over the variable.
 */
import {type Attributes} from '@opentelemetry/api';

import {
  getCurrentTurn,
  type LLM,
  type Message,
  runIsolated,
  Turn,
  type Usage,
} from '../genai';
import {ATTR_ERROR_TYPE, ATTR_GEN_AI_RESPONSE_ID} from '../genai/semconv';
import {asOtelAttributes, libraryIntegration} from './integrationMetadata';
import {
  addCJSInstrumentation,
  addESMInstrumentation,
  suppressLoadOrderWarning,
} from './instrumentations';

const PROVIDER_NAME = 'typesafe';
const AGENT_NAME = 'typesafe SDK';
const OPERATION = 'typesafe.system_one';
const QUESTIONS_ATTR = 'typesafe.questions';
const REQUEST_ID_HEADER = 'x-typesafe-request-id';
const MODULE_NAME = '@typesafe-ai/sdk';
const CJS_SUBPATH = 'dist/index.cjs';
const VERSION_RANGE = '>=0.6.0 <0.7.0';
const CAPTURE_ENV = 'OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT';
const CAPTURE_OFF = new Set(['0', 'false', 'no', 'off']);
const HTTP_STATUS = 'http.response.status_code';
const PATCHED = Symbol.for('weave.typesafe.patched');
const barriers = new WeakSet<object>();
const BARRIER_METHODS = [
  'then',
  'catch',
  'finally',
  'asResponse',
  'withResponse',
  'map',
] as const;

const INTEGRATION_ATTRS = asOtelAttributes(
  libraryIntegration(PROVIDER_NAME, {packageName: 'typesafe-sdk'})
);

const captureSettings = new WeakMap<object, boolean>();

export type TypeSafeWrapOptions = {
  /** When set, overrides the capture-content environment variable for this client. */
  captureContent?: boolean;
};

type Trace = {
  llm: LLM;
  turn: Turn | null;
  ownsTurn: boolean;
  capture: boolean;
  closed: boolean;
};

type ParsedBody = {
  body: unknown;
  requestId?: string;
};

function envCapture(): boolean {
  const raw = process.env[CAPTURE_ENV];
  if (raw == null) {
    return true;
  }
  return !CAPTURE_OFF.has(raw.trim().toLowerCase());
}

function captureFor(client: object): boolean {
  if (captureSettings.has(client)) {
    return captureSettings.get(client) === true;
  }
  return envCapture();
}

function activeTurn(): Turn | undefined {
  const turn = getCurrentTurn();
  if (!turn || (turn as unknown as {_ended?: boolean})._ended) {
    return undefined;
  }
  return turn;
}

function modelName(client: any, request: any): string {
  const requested = request?.model ?? client?.defaultModel ?? 'jev-latest';
  return typeof requested === 'string' ? requested : '';
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortValue);
  }
  if (!value || typeof value !== 'object') {
    return value;
  }
  const sorted: Record<string, unknown> = {};
  for (const key of Object.keys(value as Record<string, unknown>).sort()) {
    const item = (value as Record<string, unknown>)[key];
    if (item !== undefined) {
      sorted[key] = sortValue(item);
    }
  }
  return sorted;
}

function stateMessage(state: unknown): Message {
  if (typeof state === 'string') {
    return {role: 'user', content: state};
  }
  return {
    role: 'user',
    parts: [{type: 'text', content: JSON.stringify(sortValue(state))}],
  };
}

function questionItem(
  id: string | number,
  question: unknown
): Record<string, unknown> {
  const item: Record<string, unknown> = {id};
  if (question && typeof question === 'object' && !Array.isArray(question)) {
    Object.assign(item, question);
    return item;
  }
  item.value = question;
  return item;
}

function questionsJson(questions: unknown): string | undefined {
  if (Array.isArray(questions)) {
    return JSON.stringify(
      questions.map((question, index) => questionItem(index, question))
    );
  }
  if (!questions || typeof questions !== 'object') {
    return undefined;
  }
  return JSON.stringify(
    Object.entries(questions as Record<string, unknown>).map(([id, question]) =>
      questionItem(id, question)
    )
  );
}

function answersMessage(body: unknown): Message | undefined {
  if (!body || typeof body !== 'object' || !('answers' in body)) {
    return undefined;
  }
  const answers = (body as {answers?: unknown}).answers;
  if (answers == null) {
    return undefined;
  }
  return {
    role: 'assistant',
    parts: [{type: 'text', content: JSON.stringify(sortValue(answers))}],
  };
}

function usageFrom(body: unknown): Usage | undefined {
  if (!body || typeof body !== 'object' || !('usage' in body)) {
    return undefined;
  }
  const usage = (body as {usage?: unknown}).usage;
  if (!usage || typeof usage !== 'object') {
    return undefined;
  }
  const record = usage as {input_tokens?: unknown; output_tokens?: unknown};
  const parsed: Usage = {};
  if (typeof record.input_tokens === 'number') {
    parsed.inputTokens = record.input_tokens;
  }
  if (typeof record.output_tokens === 'number') {
    parsed.outputTokens = record.output_tokens;
  }
  if (parsed.inputTokens === undefined && parsed.outputTokens === undefined) {
    return undefined;
  }
  return parsed;
}

function responseModel(body: unknown): string | undefined {
  if (!body || typeof body !== 'object') {
    return undefined;
  }
  const model = (body as {model?: unknown}).model;
  return typeof model === 'string' && model ? model : undefined;
}

function stampProvenance(span: {
  setAttributes(attributes: Attributes): unknown;
}): void {
  span.setAttributes({
    ...INTEGRATION_ATTRS,
    'weave.integration.operation': OPERATION,
  });
}

function errorTypeName(error: unknown): string {
  if (error instanceof Error && error.name) {
    return error.name;
  }
  if (error && typeof error === 'object') {
    const name = (error as {name?: unknown}).name;
    if (typeof name === 'string' && name) {
      return name;
    }
  }
  return 'Error';
}

function errorStatus(error: unknown): number | undefined {
  if (!error || typeof error !== 'object') {
    return undefined;
  }
  const status = (error as {status?: unknown}).status;
  return typeof status === 'number' && Number.isInteger(status)
    ? status
    : undefined;
}

function errorRequestId(error: unknown): string | undefined {
  if (!error || typeof error !== 'object') {
    return undefined;
  }
  const record = error as {
    requestId?: unknown;
    headers?: {get?: (name: string) => unknown};
  };
  if (typeof record.requestId === 'string' && record.requestId) {
    return record.requestId;
  }
  try {
    const value = record.headers?.get?.(REQUEST_ID_HEADER);
    return typeof value === 'string' && value ? value : undefined;
  } catch {
    return undefined;
  }
}

function sanitizedError(error: unknown): Error {
  const safe = new Error('');
  safe.name = errorTypeName(error);
  return safe;
}

/** Mark a span failed without copying the provider error text. */
function stampError(span: LLM | Turn, error: unknown): void {
  const attributes: Attributes = {
    [ATTR_ERROR_TYPE]: errorTypeName(error),
  };
  const status = errorStatus(error);
  if (status !== undefined) {
    attributes[HTTP_STATUS] = status;
  }
  const requestId = errorRequestId(error);
  if (requestId) {
    attributes[ATTR_GEN_AI_RESPONSE_ID] = requestId;
  }
  span.setAttributes(attributes);
  // recordError also writes an exception event. The message is empty, so the
  // response body is not copied. end({error}) would copy error.message.
  span.recordError(sanitizedError(error));
}

function safeEnd(span: {end?: () => void} | null): void {
  try {
    span?.end?.();
  } catch {
    console.warn('TypeSafe span setup failed');
  }
}

function openTrace(
  client: object,
  request: any,
  parent: Turn | undefined
): Trace | null {
  let turn: Turn | null = null;
  let ownsTurn = false;
  let llm: LLM | null = null;
  try {
    const capture = captureFor(client);
    const model = modelName(client, request);
    if (parent) {
      turn = parent;
      llm = parent.startLLM({model, providerName: PROVIDER_NAME});
    } else {
      turn = Turn.create({agentName: AGENT_NAME});
      ownsTurn = true;
      llm = turn.startLLM({model, providerName: PROVIDER_NAME});
    }
    if (capture) {
      llm.inputMessages = [stateMessage(request?.state)];
    }
    stampProvenance(llm);
    if (ownsTurn) {
      stampProvenance(turn);
    }
    if (capture) {
      const questions = questionsJson(request?.questions);
      if (questions !== undefined) {
        llm.setAttributes({[QUESTIONS_ATTR]: questions});
      }
    }
    return {llm, turn, ownsTurn, capture, closed: false};
  } catch {
    console.warn('TypeSafe span setup failed');
    safeEnd(llm);
    if (ownsTurn) {
      safeEnd(turn);
    }
    return null;
  }
}

function fill(trace: Trace, parsed: ParsedBody): void {
  const record: {
    outputType: string;
    responseModel?: string;
    usage?: Usage;
    responseId?: string;
    outputMessages?: Message[];
  } = {outputType: 'json'};
  const model = responseModel(parsed.body);
  if (model) {
    record.responseModel = model;
  }
  const usage = usageFrom(parsed.body);
  if (usage) {
    record.usage = usage;
  }
  if (parsed.requestId) {
    record.responseId = parsed.requestId;
  }
  if (trace.capture) {
    const answers = answersMessage(parsed.body);
    if (answers) {
      record.outputMessages = [answers];
    }
  }
  trace.llm.record(record);
}

function close(trace: Trace, error?: unknown): void {
  if (trace.closed) {
    return;
  }
  trace.closed = true;
  if (error !== undefined) {
    stampError(trace.llm, error);
    if (trace.ownsTurn && trace.turn) {
      stampError(trace.turn, error);
    }
  }
  trace.llm.end();
  if (trace.ownsTurn && trace.turn) {
    trace.turn.end();
  }
}

function isBarrierTarget(value: unknown): value is Record<string, any> {
  if (!value || (typeof value !== 'object' && typeof value !== 'function')) {
    return false;
  }
  return BARRIER_METHODS.every(
    name => typeof (value as Record<string, unknown>)[name] === 'function'
  );
}

function headerRequestId(response: {
  headers?: {get?: (name: string) => string | null};
}): string | undefined {
  try {
    const value = response.headers?.get?.(REQUEST_ID_HEADER);
    return typeof value === 'string' && value ? value : undefined;
  } catch {
    return undefined;
  }
}

function installBarrier(
  promise: Record<string, any>,
  done: Promise<void>
): void {
  if (barriers.has(promise)) {
    return;
  }
  barriers.add(promise);
  for (const name of [
    'then',
    'catch',
    'finally',
    'asResponse',
    'withResponse',
  ] as const) {
    const original = promise[name].bind(promise);
    promise[name] = (...args: unknown[]) => done.then(() => original(...args));
  }
  const originalMap = promise.map.bind(promise);
  promise.map = (fn: unknown) => {
    const mapped = originalMap(fn);
    if (isBarrierTarget(mapped)) {
      installBarrier(mapped, done);
    }
    return mapped;
  };
}

function arm(promise: Record<string, any>, trace: Trace): void {
  let responsePromise: Promise<unknown>;
  try {
    responsePromise = promise.asResponse.call(promise);
  } catch {
    console.warn('TypeSafe span capture failed');
    close(trace, undefined);
    return;
  }
  if (!responsePromise || typeof responsePromise.then !== 'function') {
    console.warn('TypeSafe span capture failed');
    close(trace, undefined);
    return;
  }

  let resolveDone = () => {};
  const done = new Promise<void>(resolve => {
    resolveDone = resolve;
  });
  let settled = false;
  const finish = (error?: unknown, parsed?: ParsedBody) => {
    if (!settled) {
      settled = true;
      if (parsed) {
        try {
          fill(trace, parsed);
        } catch {
          console.warn('TypeSafe span capture failed');
        }
      }
      try {
        close(trace, error);
      } catch {
        console.warn('TypeSafe span capture failed');
      }
    }
    resolveDone();
  };

  responsePromise.then(
    response => {
      void readResponse(response, finish);
    },
    error => finish(error)
  );
  installBarrier(promise, done);
}

async function readResponse(
  response: unknown,
  finish: (error?: unknown, parsed?: ParsedBody) => void
): Promise<void> {
  try {
    if (
      !response ||
      typeof response !== 'object' ||
      typeof (response as {clone?: unknown}).clone !== 'function'
    ) {
      console.warn('TypeSafe span capture failed');
      finish();
      return;
    }
    const http = response as {
      clone: () => {json: () => Promise<unknown>};
      headers?: {get?: (name: string) => string | null};
    };
    const body = await http.clone().json();
    finish(undefined, {body, requestId: headerRequestId(http)});
  } catch {
    console.warn('TypeSafe span capture failed');
    finish();
  }
}

function traceCall(
  original: (...args: any[]) => unknown,
  client: any,
  request: any,
  options: unknown
): unknown {
  const parent = activeTurn();
  return runIsolated(() => {
    const trace = openTrace(client, request, parent);
    if (!trace) {
      return Reflect.apply(original, client, [request, options]);
    }
    let result: unknown;
    try {
      result = Reflect.apply(original, client, [request, options]);
    } catch (error) {
      close(trace, error);
      throw error;
    }
    if (!isBarrierTarget(result)) {
      console.warn('TypeSafe span capture failed');
      close(trace, undefined);
      return result;
    }
    arm(result, trace);
    return result;
  });
}

function patchSystemOne(target: any): void {
  if (target?.[PATCHED] || typeof target?.systemOne !== 'function') {
    return;
  }
  const original = target.systemOne;
  Object.defineProperty(target, PATCHED, {value: true, configurable: true});
  function wrapped(this: any, request: any, options?: unknown) {
    return traceCall(original, this, request, options);
  }
  Object.defineProperty(target, 'systemOne', {
    value: wrapped,
    writable: true,
    configurable: true,
  });
}

/** Patch the TypeSafe client class on a CJS or ESM module namespace. */
export function patchTypeSafeModule(exports: any): any {
  const client =
    exports?.TypeSafeClient ??
    exports?.default?.TypeSafeClient ??
    exports?.default;
  if (typeof client?.prototype?.systemOne === 'function') {
    patchSystemOne(client.prototype);
  }
  return exports;
}

/**
 * Trace `systemOne` on this client. Returns the same client.
 *
 * A second call with `captureContent` updates that client's setting. When the
 * module hook has already patched the prototype, this only updates settings.
 */
export function wrapTypeSafe<T extends object>(
  client: T,
  options?: TypeSafeWrapOptions
): T {
  suppressLoadOrderWarning(MODULE_NAME);
  if (options && options.captureContent !== undefined) {
    captureSettings.set(client, options.captureContent);
  }
  const proto = Object.getPrototypeOf(client);
  if (proto?.[PATCHED] || (client as any)[PATCHED]) {
    if (!(client as any)[PATCHED]) {
      Object.defineProperty(client, PATCHED, {value: true, configurable: true});
    }
    return client;
  }
  patchSystemOne(client);
  return client;
}

/** Register the loader hooks. Does not import `@typesafe-ai/sdk`. */
export function instrumentTypeSafe(): void {
  addCJSInstrumentation({
    moduleName: MODULE_NAME,
    subPath: CJS_SUBPATH,
    version: VERSION_RANGE,
    hook: patchTypeSafeModule,
    // The patch is on the client prototype, so it reaches clients created
    // before the hook ran.
    reachesEarlierReferences: true,
  });
  addESMInstrumentation({
    moduleName: MODULE_NAME,
    version: VERSION_RANGE,
    hook: patchTypeSafeModule,
  });
}
