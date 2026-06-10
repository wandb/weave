/**
 * Weave integration for the Google Agent Development Kit for TypeScript
 * (`@google/adk`).
 *
 * The integration is an ADK *plugin*: ADK dispatches plugin callbacks at its
 * runner / model / tool lifecycle boundaries, and `WeaveAdkPlugin` mirrors
 * those boundaries into Weave calls (`saveCallStart` / `saveCallEnd`), the
 * same transport the OpenAI Agents integration uses.
 *
 * Why a plugin rather than ADK's OpenTelemetry spans: riding ADK's native
 * OTel tracing would require Weave to register the process-global OTel
 * TracerProvider and ContextManager, which would silently break any user
 * observability stack registered later. Plugin callbacks fire regardless of
 * OTel setup and hand us live `LlmRequest` / `LlmResponse` / tool objects
 * instead of JSON-serialized span attributes.
 *
 * Note on agent nesting: as of `@google/adk` 1.2.0 the runner never
 * dispatches plugin `beforeAgentCallback` / `afterAgentCallback` (the
 * `PluginManager` methods exist but have no call sites — only run, model,
 * tool and event callbacks fire). Per-agent calls are therefore synthesized
 * lazily from `agentName` on model/tool callbacks, parented by walking the
 * agent tree captured at run start. The agent callbacks are still
 * implemented so nesting tightens automatically once ADK wires them up.
 *
 * Usage (automatic — module hooks patch `Runner` when `@google/adk` loads):
 * ```typescript
 * import * as weave from 'weave';
 * import {LlmAgent, InMemoryRunner} from '@google/adk';
 *
 * await weave.init('my-project');
 * const runner = new InMemoryRunner(myAgent); // auto-traced
 * ```
 *
 * Usage (explicit — works without module hooks, e.g. bundlers):
 * ```typescript
 * import {WeaveAdkPlugin} from 'weave';
 *
 * const runner = new Runner({appName, agent, sessionService,
 *                            plugins: [new WeaveAdkPlugin()]});
 * ```
 */

import {uuidv7} from 'uuidv7';
import {getGlobalClient} from '../clientApi';
import {globalSingleton} from '../utils/globalSingleton';
import {warnOnce} from '../utils/warnOnce';
import type {WeaveClient} from '../weaveClient';
import type {
  AdkBaseAgent,
  AdkBaseTool,
  AdkCallbackContext,
  AdkContent,
  AdkEvent,
  AdkInvocationContext,
  AdkLlmRequest,
  AdkLlmResponse,
  AdkRunnerLike,
  AdkToolContext,
  AdkUsageMetadata,
} from './googleAdk.types';
import {addCJSInstrumentation, addESMInstrumentation} from './instrumentations';

/** Name ADK's PluginManager registers the plugin under (must be unique). */
export const WEAVE_ADK_PLUGIN_NAME = 'weave';

const OP_INVOCATION = 'google.adk.invocation';
const OP_INVOKE_AGENT = 'google.adk.invoke_agent';
const OP_CALL_LLM = 'google.adk.call_llm';
const OP_EXECUTE_TOOL = 'google.adk.execute_tool';

const UNKNOWN_MODEL = 'unknown';
// Output status recorded on calls force-closed at run end / process exit.
const STATUS_INTERRUPTED = 'interrupted';
// Defensive bound when walking `parentAgent` chains (they should be trees).
const MAX_AGENT_ANCESTRY_DEPTH = 100;

// The `@google/adk` versions this integration is tested against. The hook is
// defensive (every patched surface is typeof-guarded), so a minor bump that
// keeps the plugin API intact will keep working.
const ADK_VERSION_RANGE = '>= 1.0.0';
// `@google/adk` is `"type": "module"`; its `require` condition resolves here.
const ADK_CJS_SUBPATH = 'dist/cjs/index.js';

const WARN_KEY_PLUGIN_ERROR = 'weave-adk-plugin-error';

interface CallData {
  callId: string;
  parentId: string | null;
}

interface ModelCallData extends CallData {
  model: string;
}

interface InvocationState {
  rootCall: CallData;
  traceId: string;
  rootAgent: AdkBaseAgent | null;
  /** agentName → synthesized invoke_agent call. */
  agentCalls: Map<string, CallData>;
  /** Creation order of agentCalls keys; closed in reverse (children first). */
  agentCallOrder: string[];
  /** agentName → in-flight call_llm call. */
  modelCalls: Map<string, ModelCallData>;
  /** functionCallId (or synthetic key) → in-flight execute_tool call. */
  toolCalls: Map<string, CallData>;
  /** Open tool keys, innermost last — fallback parent for agents that are
   *  not in the agent tree (e.g. agents wrapped as AgentTool). */
  openToolKeys: string[];
  /** Per-(agent, tool) FIFO of synthetic keys when functionCallId is absent. */
  syntheticToolKeys: Map<string, string[]>;
  /** Content of the last non-partial event — becomes the root call output. */
  finalContent: unknown;
  toolSeq: number;
}

// ---------------------------------------------------------------------------
// Serialization helpers
// ---------------------------------------------------------------------------

/**
 * Converts foreign (user/ADK-owned) values into JSON-safe plain data.
 * Functions are dropped, bigints stringified, cycles replaced — a cycle or
 * non-serializable value in a tool payload must never break call logging.
 */
function toJsonSafe(value: unknown): any {
  if (
    value == null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return value ?? null;
  }
  const seen = new WeakSet<object>();
  const replacer = (_key: string, val: any) => {
    if (typeof val === 'bigint') {
      return val.toString();
    }
    if (val !== null && typeof val === 'object') {
      if (seen.has(val)) {
        return '[Circular]';
      }
      seen.add(val);
    }
    return val;
  };
  try {
    const text = JSON.stringify(value, replacer);
    return text === undefined ? null : JSON.parse(text);
  } catch {
    try {
      return String(value);
    } catch {
      return null;
    }
  }
}

/** Strips base64 `inlineData` parts, mirroring ADK's own trace builder. */
function stripInlineData(content: AdkContent): AdkContent {
  if (!Array.isArray(content?.parts)) {
    return content;
  }
  return {
    ...content,
    parts: content.parts.filter(part => part == null || !part.inlineData),
  };
}

/**
 * Sanitized `LlmRequest` for call inputs. Mirrors ADK's
 * `buildLlmRequestForTrace`: drop `responseSchema` (commonly a Zod schema,
 * not serializable) and inline binary data; keep model, config and contents.
 */
function sanitizeLlmRequest(llmRequest: AdkLlmRequest): Record<string, any> {
  const inputs: Record<string, any> = {
    model: llmRequest?.model ?? null,
  };
  const config = llmRequest?.config;
  if (config != null && typeof config === 'object') {
    const {responseSchema: _responseSchema, ...cleanConfig} = config as Record<
      string,
      unknown
    >;
    inputs.config = toJsonSafe(cleanConfig);
  }
  const contents = Array.isArray(llmRequest?.contents)
    ? llmRequest.contents
    : [];
  inputs.contents = toJsonSafe(contents.map(stripInlineData));
  return inputs;
}

function sanitizeLlmResponse(llmResponse: AdkLlmResponse): any {
  const content = llmResponse?.content;
  if (content != null && Array.isArray(content.parts)) {
    return toJsonSafe({...llmResponse, content: stripInlineData(content)});
  }
  return toJsonSafe(llmResponse);
}

/** Maps Gemini usage metadata to Weave's usage schema (see geminiSummarizer). */
function usageFromMetadata(
  usageMetadata: AdkUsageMetadata | undefined
): Record<string, number> | null {
  if (usageMetadata == null) {
    return null;
  }
  const usage: Record<string, number> = {};
  if (usageMetadata.promptTokenCount != null) {
    usage.prompt_tokens = usageMetadata.promptTokenCount;
  }
  if (usageMetadata.candidatesTokenCount != null) {
    usage.completion_tokens = usageMetadata.candidatesTokenCount;
  }
  if (usageMetadata.totalTokenCount != null) {
    usage.total_tokens = usageMetadata.totalTokenCount;
  }
  if (Object.keys(usage).length === 0) {
    return null;
  }
  usage.requests = 1;
  return usage;
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
 * An ADK plugin that logs runner invocations, agent runs, model calls and
 * tool executions to Weave.
 *
 * Implements the full `BasePlugin` callback surface structurally (ADK's
 * `PluginManager` calls every callback unconditionally and treats any
 * non-`undefined` return as a short-circuit, so every callback here swallows
 * its own errors and returns `undefined`).
 */
export class WeaveAdkPlugin {
  readonly name = WEAVE_ADK_PLUGIN_NAME;

  private readonly invocations = new Map<string, InvocationState>();
  private beforeExitRegistered = false;

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

      const callId = uuidv7();
      const traceId = uuidv7();
      const rootAgent = ic.agent ?? null;

      client.saveCallStart({
        project_id: client.projectId,
        id: callId,
        op_name: OP_INVOCATION,
        display_name: rootAgent?.name ? `invocation ${rootAgent.name}` : null,
        trace_id: traceId,
        parent_id: null,
        started_at: new Date().toISOString(),
        inputs: {
          user_message: toJsonSafe(ic.userContent ?? null),
          agent_name: rootAgent?.name ?? null,
          app_name: ic.session?.appName ?? null,
          user_id: ic.session?.userId ?? null,
          session_id: ic.session?.id ?? null,
        },
        attributes: {
          kind: 'agent',
          adk_invocation_id: invocationId,
        },
      });

      this.invocations.set(invocationId, {
        rootCall: {callId, parentId: null},
        traceId,
        rootAgent,
        agentCalls: new Map(),
        agentCallOrder: [],
        modelCalls: new Map(),
        toolCalls: new Map(),
        openToolKeys: [],
        syntheticToolKeys: new Map(),
        finalContent: null,
        toolSeq: 0,
      });
      this.registerBeforeExitHookOnce();
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
      if (!state || !event || event.partial || event.content == null) {
        return;
      }
      state.finalContent = toJsonSafe(event.content);
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
      const client = getGlobalClient();
      if (!state || !invocationId || !client) {
        return;
      }
      this.finishInvocation(client, state, state.finalContent);
      this.invocations.delete(invocationId);
    });
    return undefined;
  }

  // -------------------------------------------------------------------------
  // Agent lifecycle
  //
  // Not dispatched by @google/adk 1.2.0 (no PluginManager call sites), but
  // implemented so agent timing becomes exact when ADK wires them up.
  // -------------------------------------------------------------------------

  async beforeAgentCallback(params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    this.guard(() => {
      const client = getGlobalClient();
      const state = this.invocations.get(params.callbackContext?.invocationId);
      if (!client || !state || !params.agent?.name) {
        return;
      }
      this.ensureAgentCall(client, state, params.agent.name);
    });
    return undefined;
  }

  async afterAgentCallback(params: {
    agent: AdkBaseAgent;
    callbackContext: AdkCallbackContext;
  }): Promise<undefined> {
    this.guard(() => {
      const client = getGlobalClient();
      const state = this.invocations.get(params.callbackContext?.invocationId);
      const agentName = params.agent?.name;
      if (!client || !state || !agentName) {
        return;
      }
      const call = state.agentCalls.get(agentName);
      if (!call) {
        return;
      }
      client.saveCallEnd({
        project_id: client.projectId,
        id: call.callId,
        ended_at: new Date().toISOString(),
        output: null,
        summary: {},
      });
      // Remove so a LoopAgent re-run of the same agent opens a fresh call.
      state.agentCalls.delete(agentName);
      state.agentCallOrder = state.agentCallOrder.filter(
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
      const client = getGlobalClient();
      const ctx = params.callbackContext;
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!client || !state || !ctx?.agentName) {
        return;
      }
      // A second model call by the same agent only starts after the first
      // finished (the flow is sequential per agent), so agentName cannot
      // collide; if a stale in-flight call somehow exists, leave it to the
      // afterRun cleanup rather than corrupting its entry.
      if (state.modelCalls.has(ctx.agentName)) {
        return;
      }
      const agentCall = this.ensureAgentCall(client, state, ctx.agentName);
      const model = params.llmRequest?.model ?? UNKNOWN_MODEL;
      const callId = uuidv7();
      client.saveCallStart({
        project_id: client.projectId,
        id: callId,
        op_name: OP_CALL_LLM,
        display_name: model,
        trace_id: state.traceId,
        parent_id: agentCall.callId,
        started_at: new Date().toISOString(),
        inputs: sanitizeLlmRequest(params.llmRequest ?? {}),
        attributes: {
          kind: 'llm',
          adk_agent_name: ctx.agentName,
        },
      });
      state.modelCalls.set(ctx.agentName, {
        callId,
        parentId: agentCall.callId,
        model,
      });
    });
    return undefined;
  }

  async afterModelCallback(params: {
    callbackContext: AdkCallbackContext;
    llmResponse: AdkLlmResponse;
  }): Promise<undefined> {
    this.guard(() => {
      const client = getGlobalClient();
      const ctx = params.callbackContext;
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!client || !state || !ctx?.agentName) {
        return;
      }
      const response = params.llmResponse;
      // Streaming yields partial chunks before a final aggregated response;
      // only the final one carries the full content and usage.
      if (response?.partial) {
        return;
      }
      const inflight = state.modelCalls.get(ctx.agentName);
      if (!inflight) {
        return;
      }
      const usage = usageFromMetadata(response?.usageMetadata);
      const exception = response?.errorCode
        ? `${response.errorCode}: ${response.errorMessage ?? ''}`
        : undefined;
      client.saveCallEnd({
        project_id: client.projectId,
        id: inflight.callId,
        ended_at: new Date().toISOString(),
        output: response == null ? null : sanitizeLlmResponse(response),
        exception,
        summary: usage ? {usage: {[inflight.model]: usage}} : {},
      });
      state.modelCalls.delete(ctx.agentName);
    });
    return undefined;
  }

  async onModelErrorCallback(params: {
    callbackContext: AdkCallbackContext;
    llmRequest: AdkLlmRequest;
    error: Error;
  }): Promise<undefined> {
    this.guard(() => {
      const client = getGlobalClient();
      const ctx = params.callbackContext;
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!client || !state || !ctx?.agentName) {
        return;
      }
      const inflight = state.modelCalls.get(ctx.agentName);
      if (!inflight) {
        return;
      }
      client.saveCallEnd({
        project_id: client.projectId,
        id: inflight.callId,
        ended_at: new Date().toISOString(),
        output: null,
        exception: errorToExceptionString(params.error),
        summary: {},
      });
      state.modelCalls.delete(ctx.agentName);
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
      const client = getGlobalClient();
      const ctx = params.toolContext;
      const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
      if (!client || !state || !ctx?.agentName || !params.tool?.name) {
        return;
      }
      const agentCall = this.ensureAgentCall(client, state, ctx.agentName);
      let key = ctx.functionCallId;
      if (!key || state.toolCalls.has(key)) {
        // No functionCallId (or a duplicate): mint a synthetic key and queue
        // it per (agent, tool) so afterToolCallback can recover it FIFO.
        key = `synthetic-${++state.toolSeq}`;
        const queueKey = syntheticQueueKey(ctx.agentName, params.tool.name);
        const queue = state.syntheticToolKeys.get(queueKey) ?? [];
        queue.push(key);
        state.syntheticToolKeys.set(queueKey, queue);
      }
      const callId = uuidv7();
      client.saveCallStart({
        project_id: client.projectId,
        id: callId,
        op_name: OP_EXECUTE_TOOL,
        display_name: params.tool.name,
        trace_id: state.traceId,
        parent_id: agentCall.callId,
        started_at: new Date().toISOString(),
        inputs: toolArgsToInputs(params.toolArgs),
        attributes: {
          kind: 'tool',
          adk_agent_name: ctx.agentName,
          tool_name: params.tool.name,
          adk_function_call_id: ctx.functionCallId ?? null,
        },
      });
      state.toolCalls.set(key, {callId, parentId: agentCall.callId});
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
      this.endToolCall(params, {output: toJsonSafe(params.result ?? null)});
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
      this.endToolCall(params, {
        output: null,
        exception: errorToExceptionString(params.error),
      });
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
   * Runs an event handler, swallowing every error. ADK's PluginManager
   * rethrows plugin callback errors into the user's agent run — a Weave
   * logging bug must never break the host application.
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
   * Returns the invoke_agent call for `agentName`, creating it (and any
   * missing ancestor agent calls) on first activity from that agent.
   */
  private ensureAgentCall(
    client: WeaveClient,
    state: InvocationState,
    agentName: string,
    depth: number = 0
  ): CallData {
    const existing = state.agentCalls.get(agentName);
    if (existing) {
      return existing;
    }

    let parentCall: CallData;
    let agent: AdkBaseAgent | undefined;
    if (state.rootAgent) {
      agent = findAgentInTree(state.rootAgent, agentName);
    }
    if (!agent || depth >= MAX_AGENT_ANCESTRY_DEPTH) {
      // Not in the agent tree (e.g. an AgentTool-wrapped agent): nest under
      // the innermost open tool call when there is one, else the root.
      parentCall = this.innermostOpenToolCall(state) ?? state.rootCall;
    } else if (
      agent === state.rootAgent ||
      !agent.parentAgent ||
      agent.parentAgent.name === agentName
    ) {
      parentCall = state.rootCall;
    } else {
      parentCall = this.ensureAgentCall(
        client,
        state,
        agent.parentAgent.name,
        depth + 1
      );
    }

    const callId = uuidv7();
    client.saveCallStart({
      project_id: client.projectId,
      id: callId,
      op_name: OP_INVOKE_AGENT,
      display_name: agentName,
      trace_id: state.traceId,
      parent_id: parentCall.callId,
      started_at: new Date().toISOString(),
      inputs: {
        agent_name: agentName,
        description: agent?.description ?? null,
      },
      attributes: {
        kind: 'agent',
      },
    });
    const call: CallData = {callId, parentId: parentCall.callId};
    state.agentCalls.set(agentName, call);
    state.agentCallOrder.push(agentName);
    return call;
  }

  private innermostOpenToolCall(state: InvocationState): CallData | null {
    for (let i = state.openToolKeys.length - 1; i >= 0; i--) {
      const call = state.toolCalls.get(state.openToolKeys[i]);
      if (call) {
        return call;
      }
    }
    return null;
  }

  private endToolCall(
    params: {
      tool: AdkBaseTool;
      toolContext: AdkToolContext;
    },
    end: {output: any; exception?: string}
  ): void {
    const client = getGlobalClient();
    const ctx = params.toolContext;
    const state = ctx ? this.invocations.get(ctx.invocationId) : undefined;
    if (!client || !state || !ctx?.agentName || !params.tool?.name) {
      return;
    }
    let key = ctx.functionCallId;
    if (!key || !state.toolCalls.has(key)) {
      const queueKey = syntheticQueueKey(ctx.agentName, params.tool.name);
      key = state.syntheticToolKeys.get(queueKey)?.shift();
    }
    // ADK always runs afterToolCallback, including after a tool error that
    // onToolErrorCallback already recorded — the map lookup misses then, and
    // the late callback is correctly ignored.
    const call = key ? state.toolCalls.get(key) : undefined;
    if (!call || !key) {
      return;
    }
    client.saveCallEnd({
      project_id: client.projectId,
      id: call.callId,
      ended_at: new Date().toISOString(),
      output: end.output,
      exception: end.exception,
      summary: {},
    });
    state.toolCalls.delete(key);
    state.openToolKeys = state.openToolKeys.filter(k => k !== key);
  }

  /**
   * Ends every call belonging to an invocation: leaves (model/tool) first,
   * then agents in reverse creation order, then the root.
   */
  private finishInvocation(
    client: WeaveClient,
    state: InvocationState,
    rootOutput: unknown
  ): void {
    const now = new Date().toISOString();

    for (const [, call] of state.modelCalls) {
      client.saveCallEnd({
        project_id: client.projectId,
        id: call.callId,
        ended_at: now,
        output: {status: STATUS_INTERRUPTED},
        summary: {},
      });
    }
    state.modelCalls.clear();

    for (const [, call] of state.toolCalls) {
      client.saveCallEnd({
        project_id: client.projectId,
        id: call.callId,
        ended_at: now,
        output: {status: STATUS_INTERRUPTED},
        summary: {},
      });
    }
    state.toolCalls.clear();
    state.openToolKeys = [];

    for (let i = state.agentCallOrder.length - 1; i >= 0; i--) {
      const call = state.agentCalls.get(state.agentCallOrder[i]);
      if (call) {
        client.saveCallEnd({
          project_id: client.projectId,
          id: call.callId,
          ended_at: now,
          output: null,
          summary: {},
        });
      }
    }
    state.agentCalls.clear();
    state.agentCallOrder = [];

    client.saveCallEnd({
      project_id: client.projectId,
      id: state.rootCall.callId,
      ended_at: now,
      output: rootOutput ?? null,
      summary: {},
    });
  }

  /**
   * Closes calls left open by invocations that never reached afterRun (e.g.
   * an exception aborted the runner). The pending call-batch timer keeps the
   * event loop alive afterwards, so the queued ends still flush.
   */
  private registerBeforeExitHookOnce(): void {
    if (this.beforeExitRegistered) {
      return;
    }
    this.beforeExitRegistered = true;
    process.once('beforeExit', () => {
      this.guard(() => {
        const client = getGlobalClient();
        if (!client) {
          return;
        }
        for (const state of this.invocations.values()) {
          this.finishInvocation(client, state, {status: STATUS_INTERRUPTED});
        }
        this.invocations.clear();
      });
    });
  }
}

function syntheticQueueKey(agentName: string, toolName: string): string {
  return `${agentName} ${toolName}`;
}

function errorToExceptionString(error: unknown): string {
  if (error instanceof Error) {
    return error.stack ?? `${error.name}: ${error.message}`;
  }
  return String(error);
}

function toolArgsToInputs(
  toolArgs: Record<string, unknown> | null | undefined
): object {
  const safe = toJsonSafe(toolArgs ?? {});
  if (safe != null && typeof safe === 'object' && !Array.isArray(safe)) {
    return safe;
  }
  return {args: safe};
}

// ---------------------------------------------------------------------------
// Automatic instrumentation
// ---------------------------------------------------------------------------

// Shared across CJS/ESM module copies so both loaders register the same
// plugin instance and see the same patch state.
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
 * (including subclasses like `InMemoryRunner`) self-registers the Weave
 * plugin on first use. Registration happens at generator-creation time,
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

/** Module-load hook shared by the CJS and ESM instrumentation paths. */
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
