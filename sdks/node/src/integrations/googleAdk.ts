/**
 * Weave integration for the Google Agent Development Kit (`@google/adk`),
 * implemented as an ADK plugin that mirrors agent runs into OpenTelemetry
 * spans and exports them to Weave's agents OTel endpoint.
 *
 * Agent nesting: ADK 1.2.0 never calls the plugin's agent callbacks, so each
 * agent's span is created on demand — the first time its name appears in a
 * model or tool callback — and nested using the agent tree captured at the
 * start of the run. The agent callbacks are still implemented, so nesting
 * improves automatically if a later ADK version starts calling them.
 *
 * Implicit: once `weave.init()` runs, ADK runners are traced automatically.
 * CJS apps must `require('weave')` before `@google/adk`.
 * ```typescript
 * import * as weave from 'weave';
 * import {InMemoryRunner} from '@google/adk';
 *
 * await weave.init('my-project');
 * const runner = new InMemoryRunner(myAgent); // auto-traced
 * ```
 *
 * Explicit (no module hooks, e.g. bundlers):
 * ```typescript
 * import {init, WeaveAdkPlugin} from 'weave';
 * import {InMemorySessionService, LlmAgent, Runner} from '@google/adk';
 *
 * // Initialize Weave first — the plugin no-ops until a Weave client exists.
 * await init('my-entity/my-project');
 *
 * const agent = new LlmAgent({
 *   name: 'weather_agent',
 *   model: 'gemini-2.5-flash',
 *   instruction: 'Answer questions about the weather.',
 * });
 *
 * const appName = 'weather_app';
 * const userId = 'user-1';
 * const sessionService = new InMemorySessionService();
 *
 * // Register the plugin on the runner — that is the whole integration.
 * const runner = new Runner({
 *   appName,
 *   agent,
 *   sessionService,
 *   plugins: [new WeaveAdkPlugin()],
 * });
 *
 * const session = await sessionService.createSession({appName, userId});
 *
 * // Iterating the generator drives the run; the plugin traces it to Weave.
 * for await (const event of runner.runAsync({
 *   userId,
 *   sessionId: session.id,
 *   newMessage: {role: 'user', parts: [{text: 'Weather in Paris?'}]},
 * })) {
 *   console.log(event);
 * }
 * ```
 */

import {
  ROOT_CONTEXT,
  SpanStatusCode,
  trace as otelTrace,
} from '@opentelemetry/api';
import type {
  Attributes,
  Context as OtelContext,
  Span as OtelSpan,
} from '@opentelemetry/api';

import type * as GoogleADK from '@google/adk';
import type {
  BaseAgent as AdkBaseAgent,
  BaseTool as AdkBaseTool,
  Context as AdkCallbackContext,
  Event as AdkEvent,
  InvocationContext as AdkInvocationContext,
  LlmRequest as AdkLlmRequest,
  LlmResponse as AdkLlmResponse,
} from '@google/adk';
import type {
  Content as AdkContent,
  ContentUnion as AdkContentUnion,
  GenerateContentConfig as AdkGenerateContentConfig,
  Part as AdkPart,
  Tool as AdkTool,
  ToolUnion as AdkToolUnion,
} from '@google/genai';
import {getGlobalClient} from '../clientApi';
import state from '../state';
import {getWeaveTracer} from '../genai/provider';
import {
  ATTR_ERROR_TYPE,
  ATTR_GEN_AI_AGENT_DESCRIPTION,
  ATTR_GEN_AI_AGENT_ID,
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_TYPE,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_CHOICE_COUNT,
  ATTR_GEN_AI_REQUEST_FREQUENCY_PENALTY,
  ATTR_GEN_AI_REQUEST_MAX_TOKENS,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_REQUEST_PRESENCE_PENALTY,
  ATTR_GEN_AI_REQUEST_SEED,
  ATTR_GEN_AI_REQUEST_STOP_SEQUENCES,
  ATTR_GEN_AI_REQUEST_TEMPERATURE,
  ATTR_GEN_AI_REQUEST_TOP_P,
  ATTR_GEN_AI_RESPONSE_FINISH_REASONS,
  ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_CALL_RESULT,
  ATTR_GEN_AI_TOOL_DEFINITIONS,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
  ATTR_GEN_AI_USAGE_TOTAL_TOKENS,
} from '../genai/semconv';
import {warnOnce} from '../utils/warnOnce';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';

/** The slice of ADK's `Runner` the instrumentation hook needs. */
type AdkRunnerLike = Pick<GoogleADK.Runner, 'pluginManager'>;

/** Name the plugin registers under in ADK's PluginManager (must be unique). */
const WEAVE_ADK_PLUGIN_NAME = 'weave';

const TRACER_NAME = 'weave.google_adk';
const WEAVE_ATTR_PREFIX = 'weave.google_adk';

const OPERATION_INVOKE_AGENT = 'invoke_agent';
const OPERATION_CHAT = 'chat';
const OPERATION_EXECUTE_TOOL = 'execute_tool';
const OUTPUT_TYPE_TEXT = 'text';
const TOOL_DEFINITION_TYPE = 'function';

const UNKNOWN_MODEL = 'unknown';
// Marks spans force-ended at run end / process exit before completing.
const ATTR_ADK_INTERRUPTED = `${WEAVE_ATTR_PREFIX}.interrupted`;
const ATTR_ADK_INVOCATION_ID = `${WEAVE_ATTR_PREFIX}.invocation_id`;
const ATTR_ADK_APP_NAME = `${WEAVE_ATTR_PREFIX}.app_name`;
const ATTR_ADK_USER_ID = `${WEAVE_ATTR_PREFIX}.user_id`;
// Defensive bound when walking `parentAgent` chains.
const MAX_AGENT_ANCESTRY_DEPTH = 100;

// ADK's own opt-out env var for message-content capture: regulated users set
// it to keep message bodies, system instructions and tool payloads off spans.
const ADK_CAPTURE_MESSAGE_CONTENT_ENV = 'ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS';
// google-genai's runtime-mode toggle; decides gemini vs vertex_ai provider.
const GOOGLE_GENAI_USE_VERTEXAI_ENV = 'GOOGLE_GENAI_USE_VERTEXAI';
const PROVIDER_NAME_GEMINI = 'gemini';
const PROVIDER_NAME_VERTEX_AI = 'vertex_ai';

// ADK uses "model" for the assistant turn; the GenAI parts model uses
// "assistant". Unrecognized roles pass through unchanged.
const ADK_TO_GENAI_ROLE: Record<string, string> = {
  user: 'user',
  model: 'assistant',
};

// Tested version range. Every patched surface is typeof-guarded, so minor
// bumps that keep the plugin API intact keep working.
const ADK_VERSION_RANGE = '>= 1.0.0';
// `@google/adk` is `"type": "module"`; its `require` condition resolves here.
const ADK_CJS_SUBPATH = 'dist/cjs/index.js';

const WARN_KEY_PLUGIN_ERROR = 'weave-adk-plugin-error';

const BEFORE_EXIT_CLEANUPS = new Set<() => void>();
let beforeExitHookRegistered = false;

type InvocationState = {
  invocationId: string;
  rootSpan: OtelSpan;
  rootAgent: AdkBaseAgent;
  conversationId: string | undefined;
  /** agentName → synthesized invoke_agent span. */
  agentSpans: Map<string, OtelSpan>;
  /** agentName → in-flight chat span. */
  modelSpans: Map<string, OtelSpan>;
  /** functionCallId (or synthetic key) → in-flight execute_tool span. */
  toolSpans: Map<string, OtelSpan>;
  /** Per-(agent, tool) FIFO of synthetic keys when functionCallId is absent. */
  syntheticToolKeys: Map<string, string[]>;
  /** Content of the last non-partial event — the root span's output. */
  finalContent: AdkContent | null;
  rootErrorType: string | undefined;
  rootErrorMessage: string | undefined;
  toolSeq: number;
};

/** A finished tool call's terminal outcome — exactly one of result or error. */
type ToolSpanOutcome =
  | {kind: 'result'; result: Record<string, unknown> | null}
  | {kind: 'error'; error: Error};

// ---------------------------------------------------------------------------
// GenAI semconv extractors (mirroring the Python google_adk integration)
// ---------------------------------------------------------------------------

/**
 * True iff message content may be written to spans. Mirrors @google/adk's own
 * `shouldAddRequestResponseToSpans` exactly — case-sensitive "true"/"1", with
 * unset/empty defaulting to capture — so Weave honors the user's opt-out the
 * same way ADK's native spans do.
 */
function captureMessageContent(): boolean {
  const value = process.env[ADK_CAPTURE_MESSAGE_CONTENT_ENV] || 'true';
  return value === 'true' || value === '1';
}

/**
 * Weave-canonical provider name for the running ADK runtime. Mirrors
 * google-genai's `stringToBoolean(GOOGLE_GENAI_USE_VERTEXAI)`, which is truthy
 * only for "true" (case-insensitive) — notably NOT "1" — so the reported
 * provider matches the backend google-genai actually selects.
 */
function providerName(): string {
  const value = process.env[GOOGLE_GENAI_USE_VERTEXAI_ENV];
  const useVertex = (value ?? '').toLowerCase() === 'true';
  return useVertex ? PROVIDER_NAME_VERTEX_AI : PROVIDER_NAME_GEMINI;
}

/**
 * Converts foreign (user/ADK-owned) values — tool args, tool results, request
 * config — into JSON-safe plain data so they can ride span attributes.
 * Returns null instead of throwing on un-serializable input: span building
 * must never break a user's run. The per-case comments inside spell out what
 * each branch guards against.
 */
function toJsonSafe(value: unknown): unknown {
  // Fast path: primitives are already JSON-safe (undefined → null so the
  // value still round-trips into an attribute).
  if (
    value == null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return value ?? null;
  }
  const seen = new WeakSet<object>();
  try {
    const text = JSON.stringify(value, (_key, val) => {
      // bigint: JSON.stringify throws on it outright; emit the digits.
      if (typeof val === 'bigint') {
        return val.toString();
      }
      // cycle: JSON.stringify throws on circular refs; break the repeat.
      if (val !== null && typeof val === 'object') {
        if (seen.has(val)) {
          return '[Circular]';
        }
        seen.add(val);
      }
      return val;
    });
    return text === undefined ? null : JSON.parse(text);
  } catch {
    // Last resort: a throwing getter or toJSON(). Drop the value rather than
    // let the exception escape into the user's run.
    return null;
  }
}

/** JSON string form for span attributes (attributes must be primitives). */
function jsonAttr(value: unknown): string {
  return JSON.stringify(toJsonSafe(value));
}

function adkRoleToGenAi(role: string | undefined): string {
  if (!role) {
    return '';
  }
  return ADK_TO_GENAI_ROLE[role] ?? role;
}

/**
 * One `Part` in the GenAI parts-model wire shape, discriminated on `type`.
 * `arguments`/`response` are `toJsonSafe` output, hence `unknown`.
 */
type WirePart =
  | {type: 'text'; content: string}
  | {type: 'blob'; mime_type: string}
  | {type: 'tool_call'; id: string; name: string; arguments: unknown}
  | {type: 'tool_call_response'; id: string; response: unknown};

/**
 * Converts one `Part` to the wire shape. Binary payloads keep the mime-type
 * signal but drop the bytes — they are not span-attribute-safe.
 */
function partToWire(part: AdkPart | null | undefined): WirePart | null {
  if (part == null) {
    return null;
  }
  if (part.inlineData) {
    return {type: 'blob', mime_type: part.inlineData.mimeType ?? ''};
  }
  if (part.functionCall) {
    return {
      type: 'tool_call',
      id: part.functionCall.id ?? '',
      name: part.functionCall.name ?? '',
      arguments: toJsonSafe(part.functionCall.args ?? {}),
    };
  }
  if (part.functionResponse) {
    return {
      type: 'tool_call_response',
      id: part.functionResponse.id ?? '',
      response: toJsonSafe(part.functionResponse.response ?? {}),
    };
  }
  if (part.text != null) {
    return {type: 'text', content: part.text};
  }
  return null;
}

function contentToParts(content: AdkContent): WirePart[] {
  const parts: WirePart[] = [];
  for (const part of content.parts ?? []) {
    const wire = partToWire(part);
    if (wire) {
      parts.push(wire);
    }
  }
  return parts;
}

function contentsToInputMessages(
  contents: AdkContent[]
): Array<Record<string, unknown>> {
  return contents.map(content => ({
    role: adkRoleToGenAi(content.role),
    parts: contentToParts(content),
  }));
}

function finishReasonString(finishReason: string | null | undefined): string {
  if (finishReason == null) {
    return '';
  }
  return finishReason.toLowerCase();
}

function contentToOutputMessage(
  content: AdkContent,
  finishReason: string | null | undefined
): Record<string, unknown> {
  return {
    role: adkRoleToGenAi(content.role) || 'assistant',
    parts: contentToParts(content),
    finish_reason: finishReasonString(finishReason),
  };
}

/** True when an ADK system-instruction element is a `Content` (has `parts`)
 *  rather than a lone `Part`. */
function isAdkContent(value: AdkContent | AdkPart): value is AdkContent {
  return 'parts' in value && Array.isArray(value.parts);
}

/**
 * Normalizes ADK's polymorphic `config.systemInstruction` (string, Content,
 * Part, or a list of those) into the parts-model wire shape.
 */
function systemInstructionParts(
  systemInstruction: AdkContentUnion | undefined
): WirePart[] {
  if (systemInstruction == null) {
    return [];
  }
  // A bare instruction string → a single text part.
  if (typeof systemInstruction === 'string') {
    return [{type: 'text', content: systemInstruction}];
  }
  // A list of any of these shapes → flatten each one recursively.
  if (Array.isArray(systemInstruction)) {
    return systemInstruction.flatMap(item => systemInstructionParts(item));
  }
  // What remains is a `Content` or a lone `Part`.
  if (isAdkContent(systemInstruction)) {
    return contentToParts(systemInstruction);
  }
  const part = partToWire(systemInstruction);
  return part ? [part] : [];
}

/** True when an ADK tool is a function-declaration `Tool` rather than a
 *  `CallableTool` (only the former carries `functionDeclarations`). */
function isAdkTool(tool: AdkToolUnion): tool is AdkTool {
  return 'functionDeclarations' in tool;
}

/** Tool definitions from `config.tools[].functionDeclarations` (schema, not
 *  user data — emitted regardless of the message-content gate). */
function toolDefinitions(
  config: AdkGenerateContentConfig
): Array<Record<string, unknown>> {
  const definitions: Array<Record<string, unknown>> = [];
  for (const tool of config.tools ?? []) {
    if (!isAdkTool(tool) || !tool.functionDeclarations) {
      continue;
    }
    for (const declaration of tool.functionDeclarations) {
      definitions.push({
        name: declaration.name ?? '',
        description: declaration.description ?? '',
        parameters: toJsonSafe(
          declaration.parameters ?? declaration.parametersJsonSchema ?? null
        ),
        type: TOOL_DEFINITION_TYPE,
      });
    }
  }
  return definitions;
}

/** Request-side GenAI attributes from an ADK `LlmRequest`. */
function setLlmRequestAttributes(
  span: OtelSpan,
  llmRequest: AdkLlmRequest
): void {
  const config = llmRequest.config;
  if (config != null) {
    if (config.temperature != null) {
      span.setAttribute(ATTR_GEN_AI_REQUEST_TEMPERATURE, config.temperature);
    }
    if (config.topP != null) {
      span.setAttribute(ATTR_GEN_AI_REQUEST_TOP_P, config.topP);
    }
    if (config.maxOutputTokens != null) {
      span.setAttribute(ATTR_GEN_AI_REQUEST_MAX_TOKENS, config.maxOutputTokens);
    }
    if (config.frequencyPenalty != null) {
      span.setAttribute(
        ATTR_GEN_AI_REQUEST_FREQUENCY_PENALTY,
        config.frequencyPenalty
      );
    }
    if (config.presencePenalty != null) {
      span.setAttribute(
        ATTR_GEN_AI_REQUEST_PRESENCE_PENALTY,
        config.presencePenalty
      );
    }
    if (config.seed != null) {
      span.setAttribute(ATTR_GEN_AI_REQUEST_SEED, config.seed);
    }
    if (config.stopSequences?.length) {
      span.setAttribute(ATTR_GEN_AI_REQUEST_STOP_SEQUENCES, [
        ...config.stopSequences,
      ]);
    }
    if (config.candidateCount != null) {
      span.setAttribute(
        ATTR_GEN_AI_REQUEST_CHOICE_COUNT,
        config.candidateCount
      );
    }
    const definitions = toolDefinitions(config);
    if (definitions.length > 0) {
      span.setAttribute(ATTR_GEN_AI_TOOL_DEFINITIONS, jsonAttr(definitions));
    }
  }
  if (captureMessageContent()) {
    const instructions = systemInstructionParts(config?.systemInstruction);
    if (instructions.length > 0) {
      span.setAttribute(
        ATTR_GEN_AI_SYSTEM_INSTRUCTIONS,
        jsonAttr(instructions)
      );
    }
    if (llmRequest.contents.length > 0) {
      span.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        jsonAttr(contentsToInputMessages(llmRequest.contents))
      );
    }
  }
}

/** Response-side GenAI attributes from an ADK `LlmResponse`. */
function setLlmResponseAttributes(
  span: OtelSpan,
  llmResponse: AdkLlmResponse
): void {
  const finishReason = finishReasonString(llmResponse.finishReason);
  if (finishReason) {
    span.setAttribute(ATTR_GEN_AI_RESPONSE_FINISH_REASONS, [finishReason]);
  }
  if (captureMessageContent() && llmResponse.content != null) {
    span.setAttribute(
      ATTR_GEN_AI_OUTPUT_MESSAGES,
      jsonAttr([
        contentToOutputMessage(llmResponse.content, llmResponse.finishReason),
      ])
    );
    span.setAttribute(ATTR_GEN_AI_OUTPUT_TYPE, OUTPUT_TYPE_TEXT);
  }
  const usage = llmResponse.usageMetadata;
  if (usage == null) {
    return;
  }
  if (usage.promptTokenCount != null) {
    span.setAttribute(ATTR_GEN_AI_USAGE_INPUT_TOKENS, usage.promptTokenCount);
  }
  if (usage.candidatesTokenCount != null) {
    span.setAttribute(
      ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
      usage.candidatesTokenCount
    );
  }
  if (usage.totalTokenCount != null) {
    span.setAttribute(ATTR_GEN_AI_USAGE_TOTAL_TOKENS, usage.totalTokenCount);
  }
  if (usage.thoughtsTokenCount != null) {
    span.setAttribute(
      ATTR_GEN_AI_USAGE_REASONING_OUTPUT_TOKENS,
      usage.thoughtsTokenCount
    );
  }
  if (usage.cachedContentTokenCount != null) {
    span.setAttribute(
      ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
      usage.cachedContentTokenCount
    );
  }
}

// ---------------------------------------------------------------------------
// Agent tree helpers
// ---------------------------------------------------------------------------

/** Finds `name` in the agent tree under `root`, preferring ADK's own
 *  `findAgent` and falling back to a cycle-safe manual walk. */
function findAgentInTree(
  root: AdkBaseAgent,
  name: string
): AdkBaseAgent | undefined {
  try {
    const found = root.findAgent(name);
    if (found) {
      return found;
    }
  } catch {
    // ADK's `findAgent` recurses through `subAgents` with no cycle
    // detection, so a cyclic agent graph overflows the stack. Fall back to
    // the manual walk below, which is cycle-safe via `visited`.
  }
  const queue: AdkBaseAgent[] = [root];
  const visited = new Set<AdkBaseAgent>();
  while (queue.length > 0) {
    const agent = queue.shift()!;
    if (visited.has(agent)) {
      continue;
    }
    visited.add(agent);
    if (agent.name === name) {
      return agent;
    }
    queue.push(...agent.subAgents);
  }
  return undefined;
}

// ---------------------------------------------------------------------------
// Plugin
// ---------------------------------------------------------------------------

/**
 * ADK plugin that emits runner invocations, agent runs, model calls and tool
 * executions as GenAI-semconv OTel spans on Weave's agents pipeline.
 *
 * Implements the full `BasePlugin` surface structurally. ADK's PluginManager
 * invokes every callback, so all are present even where a callback is a no-op.
 * ADK treats any non-`undefined` return as a short-circuit, so every callback
 * swallows its own errors and returns `undefined`.
 */
export class WeaveAdkPlugin {
  readonly name = WEAVE_ADK_PLUGIN_NAME;

  private readonly invocations = new Map<string, InvocationState>();
  private readonly beforeExitCleanup = () => {
    this.guard(() => {
      for (const state of this.invocations.values()) {
        this.finishInvocation(state, {interrupted: true});
      }
      this.invocations.clear();
    });
  };

  private tracer() {
    return getWeaveTracer(TRACER_NAME);
  }

  private childContext(parent: OtelSpan): OtelContext {
    return otelTrace.setSpan(ROOT_CONTEXT, parent);
  }

  // -------------------------------------------------------------------------
  // Run lifecycle
  // -------------------------------------------------------------------------

  async onUserMessageCallback(_params: {
    invocationContext: AdkInvocationContext;
    userMessage: AdkContent;
  }): Promise<undefined> {
    return undefined;
  }

  async beforeRunCallback(params: {
    invocationContext: AdkInvocationContext;
  }): Promise<undefined> {
    this.guard(() => {
      const client = getGlobalClient();
      if (!client) {
        return;
      }
      const ic = params.invocationContext;
      const invocationId = ic.invocationId;
      if (!invocationId || this.invocations.has(invocationId)) {
        return;
      }

      // Register before the first span is created: the Weave tracer
      // provider installs its own beforeExit flush when it is first built,
      // and dangling spans must be ended before that flush runs (beforeExit
      // listeners fire in registration order).
      this.registerBeforeExitHookOnce();

      const rootAgent = ic.agent;
      const conversationId = ic.session.id;
      const attributes: Attributes = {
        [ATTR_GEN_AI_OPERATION_NAME]: OPERATION_INVOKE_AGENT,
        [ATTR_GEN_AI_PROVIDER_NAME]: providerName(),
        [ATTR_GEN_AI_AGENT_ID]: invocationId,
        [ATTR_ADK_INVOCATION_ID]: invocationId,
      };
      if (rootAgent.name) {
        attributes[ATTR_GEN_AI_AGENT_NAME] = rootAgent.name;
      }
      if (rootAgent.description) {
        attributes[ATTR_GEN_AI_AGENT_DESCRIPTION] = rootAgent.description;
      }
      if (conversationId) {
        attributes[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
      }
      if (ic.session.appName) {
        attributes[ATTR_ADK_APP_NAME] = ic.session.appName;
      }
      if (ic.session.userId) {
        attributes[ATTR_ADK_USER_ID] = ic.session.userId;
      }
      if (captureMessageContent() && ic.userContent) {
        attributes[ATTR_GEN_AI_INPUT_MESSAGES] = jsonAttr(
          contentsToInputMessages([ic.userContent])
        );
      }

      const rootSpan = this.tracer().startSpan(
        `${OPERATION_INVOKE_AGENT} ${rootAgent.name}`.trimEnd(),
        {attributes},
        ROOT_CONTEXT
      );
      this.invocations.set(invocationId, {
        invocationId,
        rootSpan,
        rootAgent,
        conversationId,
        agentSpans: new Map(),
        modelSpans: new Map(),
        toolSpans: new Map(),
        syntheticToolKeys: new Map(),
        finalContent: null,
        rootErrorType: undefined,
        rootErrorMessage: undefined,
        toolSeq: 0,
      });
    });
    return undefined;
  }

  async onEventCallback(params: {
    invocationContext: AdkInvocationContext;
    event: AdkEvent;
  }): Promise<undefined> {
    this.guard(() => {
      const state = this.invocations.get(params.invocationContext.invocationId);
      const event = params.event;
      if (!state || event.partial) {
        return;
      }
      this.recordEventError(state, event);
      this.closeShortCircuitedModelSpan(state, event);
      if (event.content == null) {
        return;
      }
      state.finalContent = event.content;
    });
    return undefined;
  }

  async afterRunCallback(params: {
    invocationContext: AdkInvocationContext;
  }): Promise<undefined> {
    this.guard(() => {
      this.endInvocation(params.invocationContext.invocationId, {
        interrupted: false,
      });
    });
    return undefined;
  }

  /**
   * Finalizes a run that never reached `afterRunCallback`. ADK only dispatches
   * `afterRunCallback` after the event loop drains normally, so a consumer that
   * breaks out of `runAsync` early — or an aborted run — leaves the invocation
   * (and its spans) open. The auto-instrument runner wrapper calls this from a
   * `finally` to close them as interrupted. Idempotent: a no-op once the run
   * has already finished (the common, fully-consumed case).
   */
  finishInterruptedInvocation(invocationId: string): void {
    this.guard(() => {
      this.endInvocation(invocationId, {interrupted: true});
    });
  }

  /** Shared teardown for normal completion and interrupted finalization. */
  private endInvocation(
    invocationId: string,
    options: {interrupted: boolean}
  ): void {
    const state = this.invocations.get(invocationId);
    if (!state) {
      return;
    }
    if (captureMessageContent() && state.finalContent) {
      state.rootSpan.setAttribute(
        ATTR_GEN_AI_OUTPUT_MESSAGES,
        jsonAttr([contentToOutputMessage(state.finalContent, null)])
      );
      state.rootSpan.setAttribute(ATTR_GEN_AI_OUTPUT_TYPE, OUTPUT_TYPE_TEXT);
    }
    this.applyRootError(state);
    this.finishInvocation(state, {interrupted: options.interrupted});
    this.invocations.delete(invocationId);
    this.unregisterBeforeExitHookIfIdle();
  }

  // -------------------------------------------------------------------------
  // Agent lifecycle (@google/adk 1.2.0 never dispatches these; no
  // PluginManager call sites)
  // -------------------------------------------------------------------------

  async beforeAgentCallback(params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    this.guard(() => {
      const state = this.invocations.get(params.callbackContext.invocationId);
      if (!state || !params.agent.name) {
        return;
      }
      this.ensureAgentSpan(state, params.agent.name);
    });
    return undefined;
  }

  async afterAgentCallback(params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    this.guard(() => {
      const state = this.invocations.get(params.callbackContext.invocationId);
      const agentName = params.agent.name;
      if (!state || !agentName) {
        return;
      }
      const span = state.agentSpans.get(agentName);
      if (!span) {
        return;
      }
      span.end();
      // Remove so a LoopAgent re-run of the same agent opens a fresh span.
      state.agentSpans.delete(agentName);
    });
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Model lifecycle
  // -------------------------------------------------------------------------

  async beforeModelCallback(params: {
    callbackContext: AdkCallbackContext;
    llmRequest: AdkLlmRequest;
  }): Promise<undefined> {
    this.guard(() => {
      const ctx = params.callbackContext;
      const state = this.invocations.get(ctx.invocationId);
      if (!state || !ctx.agentName) {
        return;
      }
      // Model calls are sequential per agent, so agentName cannot collide;
      // a stale in-flight entry is left for the afterRun cleanup.
      if (state.modelSpans.has(ctx.agentName)) {
        return;
      }
      const agentSpan = this.ensureAgentSpan(state, ctx.agentName);
      const model = params.llmRequest.model ?? UNKNOWN_MODEL;
      const attributes: Attributes = {
        [ATTR_GEN_AI_OPERATION_NAME]: OPERATION_CHAT,
        [ATTR_GEN_AI_PROVIDER_NAME]: providerName(),
        [ATTR_GEN_AI_REQUEST_MODEL]: model,
        [ATTR_GEN_AI_AGENT_NAME]: ctx.agentName,
      };
      if (state.conversationId) {
        attributes[ATTR_GEN_AI_CONVERSATION_ID] = state.conversationId;
      }
      const span = this.tracer().startSpan(
        `${OPERATION_CHAT} ${model}`,
        {attributes},
        this.childContext(agentSpan)
      );
      setLlmRequestAttributes(span, params.llmRequest);
      state.modelSpans.set(ctx.agentName, span);
    });
    return undefined;
  }

  async afterModelCallback(params: {
    callbackContext: AdkCallbackContext;
    llmResponse: AdkLlmResponse;
  }): Promise<undefined> {
    this.guard(() => {
      const ctx = params.callbackContext;
      const state = this.invocations.get(ctx.invocationId);
      if (!state || !ctx.agentName) {
        return;
      }
      const response = params.llmResponse;
      // Partial streaming chunks accumulate inside ADK; we wait for a
      // non-partial response, which carries the turn's content + usage.
      //
      // KNOWN LIMITATION (non-default SSE streaming): for a turn that emits
      // BOTH text and a tool call, ADK's NonProgressiveStrategy splits it into
      // two non-partial responses (text+usage, then the function call). We end
      // the chat span on the first, so the function call is absent from this
      // span's gen_ai.output.messages. The call still executes and is captured
      // as its own execute_tool span, so the trace is complete — only this
      // span's output list is. The default streamingMode is NONE (one
      // non-partial per turn), where this does not arise.
      if (response.partial) {
        return;
      }
      const span = state.modelSpans.get(ctx.agentName);
      if (!span) {
        return;
      }
      setLlmResponseAttributes(span, response);
      if (response.errorCode) {
        span.setAttribute(ATTR_ERROR_TYPE, response.errorCode);
        span.setStatus({
          code: SpanStatusCode.ERROR,
          message: response.errorMessage ?? response.errorCode,
        });
      }
      span.end();
      state.modelSpans.delete(ctx.agentName);
    });
    return undefined;
  }

  async onModelErrorCallback(params: {
    callbackContext: AdkCallbackContext;
    llmRequest: AdkLlmRequest;
    error: Error;
  }): Promise<undefined> {
    this.guard(() => {
      const ctx = params.callbackContext;
      const state = this.invocations.get(ctx.invocationId);
      if (!state || !ctx.agentName) {
        return;
      }
      const span = state.modelSpans.get(ctx.agentName);
      if (!span) {
        return;
      }
      span.setAttribute(ATTR_ERROR_TYPE, errorTypeOf(params.error));
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: errorMessageOf(params.error),
      });
      span.end();
      state.modelSpans.delete(ctx.agentName);
    });
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Tool lifecycle
  // -------------------------------------------------------------------------

  async beforeToolSelection(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async beforeToolCallback(params: {
    tool: AdkBaseTool;
    toolArgs: Record<string, unknown>;
    toolContext: AdkCallbackContext;
  }): Promise<undefined> {
    this.guard(() => {
      const ctx = params.toolContext;
      const state = this.invocations.get(ctx.invocationId);
      if (!state || !ctx.agentName || !params.tool.name) {
        return;
      }
      const agentSpan = this.ensureAgentSpan(state, ctx.agentName);
      let key = ctx.functionCallId;
      if (!key || state.toolSpans.has(key)) {
        // Missing/duplicate functionCallId: mint a synthetic key, recovered
        // FIFO per (agent, tool) in afterToolCallback.
        key = `synthetic-${++state.toolSeq}`;
        const queueKey = syntheticQueueKey(ctx.agentName, params.tool.name);
        const queue = state.syntheticToolKeys.get(queueKey) ?? [];
        queue.push(key);
        state.syntheticToolKeys.set(queueKey, queue);
      }
      const attributes: Attributes = {
        [ATTR_GEN_AI_OPERATION_NAME]: OPERATION_EXECUTE_TOOL,
        [ATTR_GEN_AI_PROVIDER_NAME]: providerName(),
        [ATTR_GEN_AI_TOOL_NAME]: params.tool.name,
        [ATTR_GEN_AI_AGENT_NAME]: ctx.agentName,
      };
      if (state.conversationId) {
        attributes[ATTR_GEN_AI_CONVERSATION_ID] = state.conversationId;
      }
      if (ctx.functionCallId) {
        attributes[ATTR_GEN_AI_TOOL_CALL_ID] = ctx.functionCallId;
      }
      if (captureMessageContent()) {
        attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = jsonAttr(params.toolArgs);
      }
      const span = this.tracer().startSpan(
        `${OPERATION_EXECUTE_TOOL} ${params.tool.name}`,
        {attributes},
        this.childContext(agentSpan)
      );
      state.toolSpans.set(key, span);
    });
    return undefined;
  }

  async afterToolCallback(params: {
    tool: AdkBaseTool;
    toolArgs: Record<string, unknown>;
    toolContext: AdkCallbackContext;
    result: Record<string, unknown> | null;
  }): Promise<undefined> {
    this.guard(() => {
      this.endToolSpan(params, {kind: 'result', result: params.result ?? null});
    });
    return undefined;
  }

  async onToolErrorCallback(params: {
    tool: AdkBaseTool;
    toolArgs: Record<string, unknown>;
    toolContext: AdkCallbackContext;
    error: Error;
  }): Promise<undefined> {
    this.guard(() => {
      this.endToolSpan(params, {kind: 'error', error: params.error});
    });
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Context compaction (observed but not traced)
  // -------------------------------------------------------------------------

  async beforeContextCompaction(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async afterContextCompaction(_params: unknown): Promise<undefined> {
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Internals
  // -------------------------------------------------------------------------

  /**
   * Swallows all errors: ADK rethrows plugin errors into the user's agent
   * run, and a Weave tracing bug must never break the host app.
   */
  private guard(fn: () => void): void {
    try {
      fn();
    } catch (error) {
      warnOnce(
        WARN_KEY_PLUGIN_ERROR,
        `Weave: Google ADK integration failed to record a trace event ` +
          `(further occurrences suppressed): ${error}`
      );
    }
  }

  /**
   * Returns the invoke_agent span for `agentName`, creating it and any
   * missing ancestors on first activity.
   */
  private ensureAgentSpan(
    state: InvocationState,
    agentName: string,
    depth: number = 0
  ): OtelSpan {
    const existing = state.agentSpans.get(agentName);
    if (existing) {
      return existing;
    }

    let parentSpan: OtelSpan;
    const agent = findAgentInTree(state.rootAgent, agentName);
    if (!agent || depth >= MAX_AGENT_ANCESTRY_DEPTH) {
      // Out-of-tree agent (e.g. AgentTool): nest under the innermost open
      // tool span, else the root.
      parentSpan = this.innermostOpenToolSpan(state) ?? state.rootSpan;
    } else if (
      agent === state.rootAgent ||
      !agent.parentAgent ||
      agent.parentAgent.name === agentName
    ) {
      parentSpan = state.rootSpan;
    } else {
      parentSpan = this.ensureAgentSpan(
        state,
        agent.parentAgent.name,
        depth + 1
      );
    }

    const attributes: Attributes = {
      [ATTR_GEN_AI_OPERATION_NAME]: OPERATION_INVOKE_AGENT,
      [ATTR_GEN_AI_PROVIDER_NAME]: providerName(),
      [ATTR_GEN_AI_AGENT_NAME]: agentName,
      [ATTR_GEN_AI_AGENT_ID]: state.invocationId,
    };
    if (agent?.description) {
      attributes[ATTR_GEN_AI_AGENT_DESCRIPTION] = agent.description;
    }
    // `model` is an `LlmAgent` field (a model-name string or a BaseLlm
    // instance), not on the `BaseAgent` base type; only the string form is the
    // OTel request.model (Python-integration parity).
    const agentModel = (agent as {model?: unknown} | undefined)?.model;
    if (typeof agentModel === 'string' && agentModel) {
      attributes[ATTR_GEN_AI_REQUEST_MODEL] = agentModel;
    }
    if (state.conversationId) {
      attributes[ATTR_GEN_AI_CONVERSATION_ID] = state.conversationId;
    }
    const span = this.tracer().startSpan(
      `${OPERATION_INVOKE_AGENT} ${agentName}`,
      {attributes},
      this.childContext(parentSpan)
    );
    state.agentSpans.set(agentName, span);
    return span;
  }

  private innermostOpenToolSpan(state: InvocationState): OtelSpan | null {
    // toolSpans is insertion-ordered and pruned on close, so the last open
    // span is the innermost.
    let innermost: OtelSpan | null = null;
    for (const span of state.toolSpans.values()) {
      innermost = span;
    }
    return innermost;
  }

  private endToolSpan(
    params: {
      tool: AdkBaseTool;
      toolContext: AdkCallbackContext;
    },
    outcome: ToolSpanOutcome
  ): void {
    const ctx = params.toolContext;
    const state = this.invocations.get(ctx.invocationId);
    if (!state || !ctx.agentName || !params.tool.name) {
      return;
    }
    let key = ctx.functionCallId;
    if (!key || !state.toolSpans.has(key)) {
      const queueKey = syntheticQueueKey(ctx.agentName, params.tool.name);
      key = state.syntheticToolKeys.get(queueKey)?.shift();
    }
    // afterToolCallback also fires after a tool error that
    // onToolErrorCallback already recorded; the lookup misses then and the
    // late callback is ignored.
    const span = key ? state.toolSpans.get(key) : undefined;
    if (!span || !key) {
      return;
    }
    if (outcome.kind === 'error') {
      span.setAttribute(ATTR_ERROR_TYPE, errorTypeOf(outcome.error));
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: errorMessageOf(outcome.error),
      });
    } else if (captureMessageContent()) {
      span.setAttribute(ATTR_GEN_AI_TOOL_CALL_RESULT, jsonAttr(outcome.result));
    }
    span.end();
    state.toolSpans.delete(key);
  }

  private recordEventError(state: InvocationState, event: AdkEvent): void {
    if (!event.errorCode && !event.errorMessage) {
      return;
    }
    state.rootErrorType = event.errorCode ?? 'Error';
    state.rootErrorMessage =
      event.errorMessage ?? event.errorCode ?? 'ADK event error';
  }

  /**
   * If a user/plugin before-model callback returns a cached LlmResponse, ADK
   * skips its after-model callback. The yielded event is then our only signal
   * that the chat span completed normally.
   */
  private closeShortCircuitedModelSpan(
    state: InvocationState,
    event: AdkEvent
  ): void {
    const key = this.modelSpanKeyForEvent(state, event);
    if (!key) {
      return;
    }
    const span = state.modelSpans.get(key);
    if (!span) {
      return;
    }
    if (event.content != null && captureMessageContent()) {
      span.setAttribute(
        ATTR_GEN_AI_OUTPUT_MESSAGES,
        jsonAttr([contentToOutputMessage(event.content, null)])
      );
      span.setAttribute(ATTR_GEN_AI_OUTPUT_TYPE, OUTPUT_TYPE_TEXT);
    }
    if (event.errorCode || event.errorMessage) {
      span.setAttribute(ATTR_ERROR_TYPE, event.errorCode ?? 'Error');
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: event.errorMessage ?? event.errorCode ?? 'ADK event error',
      });
    }
    span.end();
    state.modelSpans.delete(key);
  }

  private modelSpanKeyForEvent(
    state: InvocationState,
    event: AdkEvent
  ): string | undefined {
    if (event.author && state.modelSpans.has(event.author)) {
      return event.author;
    }
    if (state.modelSpans.size === 1) {
      return state.modelSpans.keys().next().value;
    }
    return undefined;
  }

  private applyRootError(state: InvocationState): void {
    if (!state.rootErrorType && !state.rootErrorMessage) {
      return;
    }
    state.rootSpan.setAttribute(
      ATTR_ERROR_TYPE,
      state.rootErrorType ?? 'Error'
    );
    state.rootSpan.setStatus({
      code: SpanStatusCode.ERROR,
      message:
        state.rootErrorMessage ?? state.rootErrorType ?? 'ADK event error',
    });
  }

  /**
   * Ends every open span of an invocation, innermost leaves before the root.
   * Leaves that never completed are marked interrupted.
   */
  private finishInvocation(
    state: InvocationState,
    options: {interrupted: boolean}
  ): void {
    for (const span of state.modelSpans.values()) {
      span.setAttribute(ATTR_ADK_INTERRUPTED, true);
      span.end();
    }
    state.modelSpans.clear();

    for (const span of state.toolSpans.values()) {
      span.setAttribute(ATTR_ADK_INTERRUPTED, true);
      span.end();
    }
    state.toolSpans.clear();

    // End agent spans children-first (reverse of creation order).
    for (const span of [...state.agentSpans.values()].reverse()) {
      span.end();
    }
    state.agentSpans.clear();

    if (options.interrupted) {
      state.rootSpan.setAttribute(ATTR_ADK_INTERRUPTED, true);
    }
    state.rootSpan.end();
  }

  /**
   * Ends spans left open by invocations that never reached afterRun (e.g.
   * runner aborted). The Weave tracer provider's own beforeExit hook runs
   * afterwards (it registers later) and flushes the exporter.
   */
  private registerBeforeExitHookOnce(): void {
    BEFORE_EXIT_CLEANUPS.add(this.beforeExitCleanup);
    if (beforeExitHookRegistered) {
      return;
    }
    beforeExitHookRegistered = true;
    process.once('beforeExit', runBeforeExitCleanups);
  }

  private unregisterBeforeExitHookIfIdle(): void {
    if (this.invocations.size > 0) {
      return;
    }
    BEFORE_EXIT_CLEANUPS.delete(this.beforeExitCleanup);
    unregisterBeforeExitHookIfUnused();
  }
}

function runBeforeExitCleanups(): void {
  beforeExitHookRegistered = false;
  const cleanups = [...BEFORE_EXIT_CLEANUPS];
  BEFORE_EXIT_CLEANUPS.clear();
  for (const cleanup of cleanups) {
    cleanup();
  }
}

function unregisterBeforeExitHookIfUnused(): void {
  if (BEFORE_EXIT_CLEANUPS.size > 0 || !beforeExitHookRegistered) {
    return;
  }
  process.off('beforeExit', runBeforeExitCleanups);
  beforeExitHookRegistered = false;
}

function syntheticQueueKey(agentName: string, toolName: string): string {
  return `${agentName}\0${toolName}`;
}

function errorTypeOf(error: Error): string {
  return error.name || 'Error';
}

function errorMessageOf(error: Error): string {
  return error.message;
}

// ---------------------------------------------------------------------------
// Automatic instrumentation
// ---------------------------------------------------------------------------

const weaveAdkRunnerPatched = Symbol.for('_weave_adk_runner_patched');

// The plugin holder lives in the shared module state (see state.ts) so CJS and
// ESM copies of this module resolve to one plugin instance.
function getSharedPlugin(): WeaveAdkPlugin {
  if (!state.integrations.googleAdk.plugin) {
    state.integrations.googleAdk.plugin = new WeaveAdkPlugin();
  }
  return state.integrations.googleAdk.plugin;
}

/** Registers the shared plugin on a runner's PluginManager, idempotently. The
 *  try/catch is the boundary safety net (instrumentation must never break a
 *  user run), so we lean on the `Runner` type rather than re-checking shape. */
function ensurePluginRegistered(runner: AdkRunnerLike): void {
  try {
    const {pluginManager} = runner;
    if (pluginManager.getPlugin(WEAVE_ADK_PLUGIN_NAME)) {
      return;
    }
    pluginManager.registerPlugin(getSharedPlugin());
  } catch {
    // Never let instrumentation break a user run.
  }
}

/**
 * Narrows a plugin resolved from ADK's PluginManager to our `WeaveAdkPlugin`.
 * `getPlugin` hands back a foreign `BasePlugin`, and CJS/ESM module copies can
 * defeat `instanceof`, so we duck-type the one method this path calls rather
 * than assert the concrete class — which also matches a user-supplied instance.
 */
function isWeavePlugin(plugin: unknown): plugin is WeaveAdkPlugin {
  return (
    typeof (plugin as {finishInterruptedInvocation?: unknown})
      ?.finishInterruptedInvocation === 'function'
  );
}

/**
 * Finalizes invocations left open because the consumer abandoned the runner's
 * event generator (early `break`/`return`) or the run aborted — ADK skips
 * `afterRunCallback` on those paths, so without this their spans never end and
 * the invocation state leaks. Resolves the plugin from the runner's own
 * PluginManager so it finalizes whichever instance is registered (the shared
 * auto-instrument plugin or a user-supplied one). A no-op on normal completion,
 * where `afterRunCallback` already finalized the invocation.
 */
function finishInterruptedInvocations(
  runner: AdkRunnerLike,
  invocationIds: Set<string>
): void {
  if (invocationIds.size === 0) {
    return;
  }
  try {
    const plugin = runner.pluginManager.getPlugin(WEAVE_ADK_PLUGIN_NAME);
    if (!isWeavePlugin(plugin)) {
      return;
    }
    for (const invocationId of invocationIds) {
      plugin.finishInterruptedInvocation(invocationId);
    }
  } catch {
    // Cleanup must never surface into the user's run.
  }
}

/**
 * Patches `Runner.prototype.runAsync` / `runEphemeral` so every runner
 * (including subclasses) self-registers the Weave plugin on first use (before
 * ADK reads the plugin list) and finalizes its invocation even when the
 * consumer abandons the event stream early.
 */
function patchRunnerClass(RunnerClass: typeof GoogleADK.Runner): void {
  // Swapping prototype methods is inherently dynamic, so view the prototype as
  // an indexable bag for the patch below.
  const proto = RunnerClass?.prototype as unknown as
    | Record<string | symbol, unknown>
    | undefined;
  if (!proto || proto[weaveAdkRunnerPatched]) {
    return;
  }
  for (const method of ['runAsync', 'runEphemeral']) {
    const original = proto[method];
    if (typeof original !== 'function') {
      continue;
    }
    proto[method] = async function* (
      this: AdkRunnerLike,
      ...args: unknown[]
    ): AsyncGenerator<AdkEvent, void> {
      ensurePluginRegistered(this);
      const invocationIds = new Set<string>();
      const events = original.apply(this, args) as AsyncIterable<AdkEvent>;
      try {
        for await (const event of events) {
          if (event?.invocationId) {
            invocationIds.add(event.invocationId);
          }
          yield event;
        }
      } finally {
        // Runs on normal completion, early `break`/`return`, throw, or abort.
        finishInterruptedInvocations(this, invocationIds);
      }
    };
  }
  Object.defineProperty(proto, weaveAdkRunnerPatched, {
    value: true,
    enumerable: false,
    configurable: true,
  });
}

/** Module-load hook shared by the CJS and ESM paths. */
export function commonPatchGoogleADK(exports: typeof GoogleADK) {
  try {
    if (exports?.Runner) {
      patchRunnerClass(exports.Runner);
    }
  } catch (error) {
    warnOnce(
      WARN_KEY_PLUGIN_ERROR,
      `Weave: failed to instrument @google/adk: ${error}`
    );
  }
  return exports;
}

export function instrumentGoogleADK() {
  addCJSInstrumentation({
    moduleName: '@google/adk',
    subPath: ADK_CJS_SUBPATH,
    version: ADK_VERSION_RANGE,
    hook: commonPatchGoogleADK,
  });
  addESMInstrumentation({
    moduleName: '@google/adk',
    version: ADK_VERSION_RANGE,
    hook: commonPatchGoogleADK,
  });
}
