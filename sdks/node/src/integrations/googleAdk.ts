/**
 * Weave integration for the Google Agent Development Kit (`@google/adk`),
 * implemented as an ADK plugin: lifecycle callbacks (run / model / tool) are
 * mirrored into OpenTelemetry spans carrying the GenAI semantic conventions,
 * exported to Weave's agents endpoint (`/agents/otel/v1/traces`) through the
 * shared Weave tracer provider — the same pipeline as the Pi coding-agent
 * integration and the openai-agents OTel processor, and the same span
 * conventions as the Python `google_adk` integration. Runs land in the
 * Weave Agents view.
 *
 * A plugin rather than ADK's native OTel spans: riding those would require
 * registering the process-global OTel TracerProvider and ContextManager,
 * silently breaking any user observability stack registered later. Plugin
 * callbacks also hand us live `LlmRequest` / `LlmResponse` / tool objects
 * instead of JSON-serialized span attributes.
 *
 * Agent nesting: `@google/adk` 1.2.0 never dispatches plugin
 * `beforeAgentCallback` / `afterAgentCallback`, so per-agent spans are
 * synthesized lazily from `agentName` on model/tool callbacks, parented via
 * the agent tree captured at run start. The agent callbacks are still
 * implemented so nesting tightens once ADK wires them up.
 *
 * Automatic usage (module hooks patch `Runner` when `@google/adk` loads):
 * ```typescript
 * import * as weave from 'weave';
 * import {InMemoryRunner} from '@google/adk';
 *
 * await weave.init('my-project');
 * const runner = new InMemoryRunner(myAgent); // auto-traced
 * ```
 *
 * Explicit usage (no module hooks, e.g. bundlers):
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

import {getGlobalClient} from '../clientApi';
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
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_RESPONSE_FINISH_REASONS,
  ATTR_GEN_AI_RESPONSE_ID,
  ATTR_GEN_AI_RESPONSE_MODEL,
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
import {globalSingleton} from '../utils/globalSingleton';
import {warnOnce} from '../utils/warnOnce';
import type {
  AdkBaseAgent,
  AdkBaseTool,
  AdkCallbackContext,
  AdkContent,
  AdkEvent,
  AdkFunctionDeclaration,
  AdkGenerateContentConfig,
  AdkInvocationContext,
  AdkLlmRequest,
  AdkLlmResponse,
  AdkPart,
  AdkRunnerLike,
  AdkToolContext,
} from './googleAdk.types';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';

/** Name the plugin registers under in ADK's PluginManager (must be unique). */
export const WEAVE_ADK_PLUGIN_NAME = 'weave';

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

interface InvocationState {
  invocationId: string;
  rootSpan: OtelSpan;
  rootAgent: AdkBaseAgent | null;
  conversationId: string | undefined;
  /** agentName → synthesized invoke_agent span. */
  agentSpans: Map<string, OtelSpan>;
  /** Creation order of agentSpans keys; ended in reverse (children first). */
  agentSpanOrder: string[];
  /** agentName → in-flight chat span. */
  modelSpans: Map<string, OtelSpan>;
  /** functionCallId (or synthetic key) → in-flight execute_tool span. */
  toolSpans: Map<string, OtelSpan>;
  /** Open tool keys, innermost last — fallback parent for out-of-tree
   *  agents (e.g. agents wrapped as AgentTool). */
  openToolKeys: string[];
  /** Per-(agent, tool) FIFO of synthetic keys when functionCallId is absent. */
  syntheticToolKeys: Map<string, string[]>;
  /** Content of the last non-partial event — the root span's output. */
  finalContent: AdkContent | null;
  rootErrorType: string | undefined;
  rootErrorMessage: string | undefined;
  toolSeq: number;
}

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
function toJsonSafe(value: unknown): any {
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

type WirePart = Record<string, unknown>;

/**
 * One `Part` in the GenAI parts-model wire shape. Binary payloads keep the
 * mime-type signal but drop the bytes — they are not span-attribute-safe.
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
    return {type: 'text', content: String(part.text)};
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

function finishReasonString(finishReason: unknown): string {
  if (finishReason == null) {
    return '';
  }
  return String(finishReason).toLowerCase();
}

function contentToOutputMessage(
  content: AdkContent,
  finishReason: unknown
): Record<string, unknown> {
  return {
    role: adkRoleToGenAi(content.role) || 'assistant',
    parts: contentToParts(content),
    finish_reason: finishReasonString(finishReason),
  };
}

/**
 * Normalizes ADK's polymorphic `config.systemInstruction` (string, Content,
 * Part, or a list of those) into the parts-model wire shape.
 */
function systemInstructionParts(systemInstruction: unknown): WirePart[] {
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
  if (typeof systemInstruction === 'object') {
    const content = systemInstruction as AdkContent;
    // A Content (has `parts`) vs. a lone Part — distinguished by `parts`.
    if (Array.isArray(content.parts)) {
      return contentToParts(content);
    }
    const part = partToWire(systemInstruction as AdkPart);
    return part ? [part] : [];
  }
  return [];
}

/** Tool definitions from `config.tools[].functionDeclarations` (schema, not
 *  user data — emitted regardless of the message-content gate). */
function toolDefinitions(
  config: AdkGenerateContentConfig
): Array<Record<string, unknown>> {
  const definitions: Array<Record<string, unknown>> = [];
  for (const tool of config.tools ?? []) {
    const declarations = (
      tool as {functionDeclarations?: AdkFunctionDeclaration[]} | null
    )?.functionDeclarations;
    if (!Array.isArray(declarations)) {
      continue;
    }
    for (const declaration of declarations) {
      definitions.push({
        name: declaration?.name ?? '',
        description: declaration?.description ?? '',
        parameters: toJsonSafe(
          declaration?.parameters ?? declaration?.parametersJsonSchema ?? null
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
  const config = llmRequest?.config;
  if (config != null) {
    if (config.temperature != null) {
      span.setAttribute('gen_ai.request.temperature', config.temperature);
    }
    if (config.topP != null) {
      span.setAttribute('gen_ai.request.top_p', config.topP);
    }
    if (config.maxOutputTokens != null) {
      span.setAttribute('gen_ai.request.max_tokens', config.maxOutputTokens);
    }
    if (config.frequencyPenalty != null) {
      span.setAttribute(
        'gen_ai.request.frequency_penalty',
        config.frequencyPenalty
      );
    }
    if (config.presencePenalty != null) {
      span.setAttribute(
        'gen_ai.request.presence_penalty',
        config.presencePenalty
      );
    }
    if (config.seed != null) {
      span.setAttribute('gen_ai.request.seed', config.seed);
    }
    if (config.stopSequences?.length) {
      span.setAttribute('gen_ai.request.stop_sequences', [
        ...config.stopSequences,
      ]);
    }
    if (config.candidateCount != null) {
      span.setAttribute('gen_ai.request.choice.count', config.candidateCount);
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
    const contents = Array.isArray(llmRequest?.contents)
      ? llmRequest.contents
      : [];
    if (contents.length > 0) {
      span.setAttribute(
        ATTR_GEN_AI_INPUT_MESSAGES,
        jsonAttr(contentsToInputMessages(contents))
      );
    }
  }
}

/** Response-side GenAI attributes from an ADK `LlmResponse`. */
function setLlmResponseAttributes(
  span: OtelSpan,
  llmResponse: AdkLlmResponse
): void {
  if (llmResponse.interactionId) {
    span.setAttribute(ATTR_GEN_AI_RESPONSE_ID, llmResponse.interactionId);
  }
  if (llmResponse.modelVersion) {
    span.setAttribute(ATTR_GEN_AI_RESPONSE_MODEL, llmResponse.modelVersion);
  }
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

/** Finds `name` in the agent tree under `root` without trusting ADK methods. */
function findAgentInTree(
  root: AdkBaseAgent,
  name: string
): AdkBaseAgent | undefined {
  if (typeof root.findAgent === 'function') {
    try {
      const found = root.findAgent(name);
      if (found) {
        return found;
      }
    } catch {
      // fall through to the manual walk
    }
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
    if (Array.isArray(agent.subAgents)) {
      queue.push(...agent.subAgents);
    }
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
 * Implements the full `BasePlugin` surface structurally. ADK treats any
 * non-`undefined` return as a short-circuit, so every callback swallows its
 * own errors and returns `undefined`.
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
      const invocationId = ic?.invocationId;
      if (!invocationId || this.invocations.has(invocationId)) {
        return;
      }

      // Register before the first span is created: the Weave tracer
      // provider installs its own beforeExit flush when it is first built,
      // and dangling spans must be ended before that flush runs (beforeExit
      // listeners fire in registration order).
      this.registerBeforeExitHookOnce();

      const rootAgent = ic.agent ?? null;
      const conversationId = ic.session?.id;
      const attributes: Attributes = {
        [ATTR_GEN_AI_OPERATION_NAME]: OPERATION_INVOKE_AGENT,
        [ATTR_GEN_AI_PROVIDER_NAME]: providerName(),
        [ATTR_GEN_AI_AGENT_ID]: invocationId,
        [ATTR_ADK_INVOCATION_ID]: invocationId,
      };
      if (rootAgent?.name) {
        attributes[ATTR_GEN_AI_AGENT_NAME] = rootAgent.name;
      }
      if (rootAgent?.description) {
        attributes[ATTR_GEN_AI_AGENT_DESCRIPTION] = rootAgent.description;
      }
      if (conversationId) {
        attributes[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
      }
      if (ic.session?.appName) {
        attributes[ATTR_ADK_APP_NAME] = ic.session.appName;
      }
      if (ic.session?.userId) {
        attributes[ATTR_ADK_USER_ID] = ic.session.userId;
      }
      if (captureMessageContent() && ic.userContent) {
        attributes[ATTR_GEN_AI_INPUT_MESSAGES] = jsonAttr(
          contentsToInputMessages([ic.userContent])
        );
      }

      const rootSpan = this.tracer().startSpan(
        `${OPERATION_INVOKE_AGENT} ${rootAgent?.name ?? ''}`.trimEnd(),
        {attributes},
        ROOT_CONTEXT
      );
      this.invocations.set(invocationId, {
        invocationId,
        rootSpan,
        rootAgent,
        conversationId,
        agentSpans: new Map(),
        agentSpanOrder: [],
        modelSpans: new Map(),
        toolSpans: new Map(),
        openToolKeys: [],
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
      const state = this.invocations.get(
        params.invocationContext?.invocationId
      );
      const event = params.event;
      if (!state || !event || event.partial) {
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
      const invocationId = params.invocationContext?.invocationId;
      const state = invocationId
        ? this.invocations.get(invocationId)
        : undefined;
      if (!state || !invocationId) {
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
      this.finishInvocation(state, {interrupted: false});
      this.invocations.delete(invocationId);
      this.unregisterBeforeExitHookIfIdle();
    });
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Agent lifecycle (not dispatched by @google/adk 1.2.0; implemented so
  // agent timing becomes exact once ADK wires them up)
  // -------------------------------------------------------------------------

  async beforeAgentCallback(params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    this.guard(() => {
      const state = this.invocations.get(params.callbackContext?.invocationId);
      if (!state || !params.agent?.name) {
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
      const state = this.invocations.get(params.callbackContext?.invocationId);
      const agentName = params.agent?.name;
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
      state.agentSpanOrder = state.agentSpanOrder.filter(
        name => name !== agentName
      );
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
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!state || !ctx?.agentName) {
        return;
      }
      // Model calls are sequential per agent, so agentName cannot collide;
      // a stale in-flight entry is left for the afterRun cleanup.
      if (state.modelSpans.has(ctx.agentName)) {
        return;
      }
      const agentSpan = this.ensureAgentSpan(state, ctx.agentName);
      const model = params.llmRequest?.model ?? UNKNOWN_MODEL;
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
      setLlmRequestAttributes(span, params.llmRequest ?? {});
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
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!state || !ctx?.agentName) {
        return;
      }
      const response = params.llmResponse;
      // Only the final (non-partial) streaming response has content + usage.
      if (response?.partial) {
        return;
      }
      const span = state.modelSpans.get(ctx.agentName);
      if (!span) {
        return;
      }
      if (response != null) {
        setLlmResponseAttributes(span, response);
        if (response.errorCode) {
          span.setAttribute(ATTR_ERROR_TYPE, response.errorCode);
          span.setStatus({
            code: SpanStatusCode.ERROR,
            message: response.errorMessage ?? response.errorCode,
          });
        }
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
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!state || !ctx?.agentName) {
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
    toolContext: AdkToolContext;
  }): Promise<undefined> {
    this.guard(() => {
      const ctx = params.toolContext;
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!state || !ctx?.agentName || !params.tool?.name) {
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
        attributes[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = jsonAttr(
          params.toolArgs ?? {}
        );
      }
      const span = this.tracer().startSpan(
        `${OPERATION_EXECUTE_TOOL} ${params.tool.name}`,
        {attributes},
        this.childContext(agentSpan)
      );
      state.toolSpans.set(key, span);
      state.openToolKeys.push(key);
    });
    return undefined;
  }

  async afterToolCallback(params: {
    tool: AdkBaseTool;
    toolArgs: Record<string, unknown>;
    toolContext: AdkToolContext;
    result: Record<string, unknown> | null;
  }): Promise<undefined> {
    this.guard(() => {
      this.endToolSpan(params, {result: params.result ?? null});
    });
    return undefined;
  }

  async onToolErrorCallback(params: {
    tool: AdkBaseTool;
    toolArgs: Record<string, unknown>;
    toolContext: AdkToolContext;
    error: Error;
  }): Promise<undefined> {
    this.guard(() => {
      this.endToolSpan(params, {error: params.error});
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
    let agent: AdkBaseAgent | undefined;
    if (state.rootAgent) {
      agent = findAgentInTree(state.rootAgent, agentName);
    }
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
    // `agent.model` is a model name string or a BaseLlm instance; only the
    // string form is the OTel request.model (Python-integration parity).
    if (typeof agent?.model === 'string' && agent.model) {
      attributes[ATTR_GEN_AI_REQUEST_MODEL] = agent.model;
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
    state.agentSpanOrder.push(agentName);
    return span;
  }

  private innermostOpenToolSpan(state: InvocationState): OtelSpan | null {
    for (let i = state.openToolKeys.length - 1; i >= 0; i--) {
      const span = state.toolSpans.get(state.openToolKeys[i]);
      if (span) {
        return span;
      }
    }
    return null;
  }

  private endToolSpan(
    params: {
      tool: AdkBaseTool;
      toolContext: AdkToolContext;
    },
    end: {result?: Record<string, unknown> | null; error?: Error}
  ): void {
    const ctx = params.toolContext;
    const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
    if (!state || !ctx?.agentName || !params.tool?.name) {
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
    if (end.error) {
      span.setAttribute(ATTR_ERROR_TYPE, errorTypeOf(end.error));
      span.setStatus({
        code: SpanStatusCode.ERROR,
        message: errorMessageOf(end.error),
      });
    } else if (captureMessageContent()) {
      span.setAttribute(ATTR_GEN_AI_TOOL_CALL_RESULT, jsonAttr(end.result));
    }
    span.end();
    state.toolSpans.delete(key);
    state.openToolKeys = state.openToolKeys.filter(k => k !== key);
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
   * Ends every span of an invocation: model/tool leaves first, then agents
   * in reverse creation order, then the root. Leaves that never completed
   * are marked interrupted.
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
    state.openToolKeys = [];

    for (let i = state.agentSpanOrder.length - 1; i >= 0; i--) {
      const span = state.agentSpans.get(state.agentSpanOrder[i]);
      if (span) {
        span.end();
      }
    }
    state.agentSpans.clear();
    state.agentSpanOrder = [];

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

function errorTypeOf(error: unknown): string {
  if (error instanceof Error && error.name) {
    return error.name;
  }
  return 'Error';
}

function errorMessageOf(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

// ---------------------------------------------------------------------------
// Automatic instrumentation
// ---------------------------------------------------------------------------

// Shared across CJS/ESM module copies so both loaders see one plugin
// instance and one patch state.
const adkInstrumentationHolder = globalSingleton<{
  plugin: WeaveAdkPlugin | null;
}>('_weave_adk_instrumentation', () => ({plugin: null}));

const weaveAdkRunnerPatched = Symbol.for('_weave_adk_runner_patched');

function getSharedPlugin(): WeaveAdkPlugin {
  if (!adkInstrumentationHolder.plugin) {
    adkInstrumentationHolder.plugin = new WeaveAdkPlugin();
  }
  return adkInstrumentationHolder.plugin;
}

/** Registers the shared plugin on a runner's PluginManager, idempotently. */
function ensurePluginRegistered(runner: AdkRunnerLike): void {
  try {
    const pluginManager = runner?.pluginManager;
    if (
      !pluginManager ||
      typeof pluginManager.getPlugin !== 'function' ||
      typeof pluginManager.registerPlugin !== 'function'
    ) {
      return;
    }
    if (pluginManager.getPlugin(WEAVE_ADK_PLUGIN_NAME)) {
      return;
    }
    pluginManager.registerPlugin(getSharedPlugin());
  } catch {
    // Never let instrumentation break a user run.
  }
}

/**
 * Patches `Runner.prototype.runAsync` / `runEphemeral` so every runner
 * (including subclasses) self-registers the Weave plugin on first use,
 * before ADK reads the plugin list.
 */
function patchRunnerClass(RunnerClass: any): void {
  const proto = RunnerClass?.prototype;
  if (!proto || proto[weaveAdkRunnerPatched]) {
    return;
  }
  for (const method of ['runAsync', 'runEphemeral']) {
    const original = proto[method];
    if (typeof original !== 'function') {
      continue;
    }
    proto[method] = function (this: AdkRunnerLike, ...args: unknown[]) {
      ensurePluginRegistered(this);
      return original.apply(this, args);
    };
  }
  Object.defineProperty(proto, weaveAdkRunnerPatched, {
    value: true,
    enumerable: false,
    configurable: true,
  });
}

/** Module-load hook shared by the CJS and ESM paths. */
export function commonPatchGoogleADK(exports: any) {
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
