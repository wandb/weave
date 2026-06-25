/**
 * Weave integration for the Google Agent Development Kit (`@google/adk`),
 * implemented as an ADK plugin that mirrors agent runs into OpenTelemetry
 * spans and exports them to Weave's agents OTel endpoint.
 *
 * Usage:
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

import {ROOT_CONTEXT, SpanStatusCode} from '@opentelemetry/api';
import type {Attributes, Span as OtelSpan} from '@opentelemetry/api';

import type {
  BaseAgent as AdkBaseAgent,
  Event as AdkEvent,
  InvocationContext as AdkInvocationContext,
} from '@google/adk';
import type {Content as AdkContent, Part as AdkPart} from '@google/genai';
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
} from '../genai/semconv';
import {warnOnce} from '../utils/warnOnce';

/** Model/tool callback context; `invocationId`/`agentName` are getters on ADK's
 *  `ReadonlyContext`, which `@google/adk` does not export as this minimal shape. */
interface AdkCallbackContext {
  invocationId: string;
  agentName: string;
}

/** Name the plugin registers under in ADK's PluginManager (must be unique). */
export const WEAVE_ADK_PLUGIN_NAME = 'weave';

const TRACER_NAME = 'weave.google_adk';
const WEAVE_ATTR_PREFIX = 'weave.google_adk';

const OPERATION_INVOKE_AGENT = 'invoke_agent';
const OUTPUT_TYPE_TEXT = 'text';

// Marks spans force-ended at run end / process exit before completing.
const ATTR_ADK_INTERRUPTED = `${WEAVE_ATTR_PREFIX}.interrupted`;
const ATTR_ADK_INVOCATION_ID = `${WEAVE_ATTR_PREFIX}.invocation_id`;
const ATTR_ADK_APP_NAME = `${WEAVE_ATTR_PREFIX}.app_name`;
const ATTR_ADK_USER_ID = `${WEAVE_ATTR_PREFIX}.user_id`;

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

const WARN_KEY_PLUGIN_ERROR = 'weave-adk-plugin-error';

const BEFORE_EXIT_CLEANUPS = new Set<() => void>();
let beforeExitHookRegistered = false;

type InvocationState = {
  invocationId: string;
  rootSpan: OtelSpan;
  conversationId: string | undefined;
  /** Content of the last non-partial event — the root span's output. */
  finalContent: AdkContent | null;
  rootErrorType: string | undefined;
  rootErrorMessage: string | undefined;
};

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
        conversationId,
        finalContent: null,
        rootErrorType: undefined,
        rootErrorMessage: undefined,
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
      const invocationId = params.invocationContext.invocationId;
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
      this.finishInvocation(state, {interrupted: false});
      this.invocations.delete(invocationId);
      this.unregisterBeforeExitHookIfIdle();
    });
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Agent lifecycle (@google/adk 1.2.0 never dispatches these; no
  // PluginManager call sites)
  // -------------------------------------------------------------------------

  async beforeAgentCallback(_params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    return undefined;
  }

  async afterAgentCallback(_params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Model lifecycle
  // -------------------------------------------------------------------------

  async beforeModelCallback(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async afterModelCallback(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async onModelErrorCallback(_params: unknown): Promise<undefined> {
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Tool lifecycle
  // -------------------------------------------------------------------------

  async beforeToolSelection(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async beforeToolCallback(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async afterToolCallback(_params: unknown): Promise<undefined> {
    return undefined;
  }

  async onToolErrorCallback(_params: unknown): Promise<undefined> {
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

  private recordEventError(state: InvocationState, event: AdkEvent): void {
    if (!event.errorCode && !event.errorMessage) {
      return;
    }
    state.rootErrorType = event.errorCode ?? 'Error';
    state.rootErrorMessage =
      event.errorMessage ?? event.errorCode ?? 'ADK event error';
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
