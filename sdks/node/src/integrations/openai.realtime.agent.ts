/**
 * Weave integration for OpenAI Agents Realtime SDK
 *
 * Observes a `RealtimeSession` (from `@openai/agents-realtime`) and produces
 * a structured Weave call tree from its event stream:
 *
 *   Realtime Session
 *   ├── Realtime Session Update      (on session.updated)
 *   ├── Generation                   (on turn_started → turn_done)
 *   │   └── Audio Out                (on audio → audio_done)
 *   └── ...
 *
 * Session lifecycle (session.created / session.updated) is sourced from
 * `session.on('transport_event')` which proxies all raw server-sent events.
 * Generation and audio lifecycle use the semantic transport-layer events
 * (`turn_started`, `turn_done`, `audio`, `audio_done`) which are emitted by
 * the transport directly and carry pre-parsed, structured payloads.
 *
 * Usage (manual):
 * ```typescript
 * import { instrumentRealtimeSession } from 'weave';
 *
 * const session = new RealtimeSession(agent);
 * instrumentRealtimeSession(session);   // attach before connect
 * await session.connect({ apiKey });
 * ```
 */

import {getGlobalClient} from '../clientApi';
import {uuidv7} from 'uuidv7';
import type {RealtimeSessionLike} from './openai.realtime.agent.types';

// ============================================================================
// Helpers
// ============================================================================

/**
 * Normalises a raw usage object (which may use camelCase or snake_case keys)
 * into the `LLMUsageSchema` shape expected by the Weave backend.
 *
 * Tries multiple commonly seen field names so the function stays robust across
 * SDK versions and API variants (Realtime, Chat Completions, Agents SDK, etc.).
 */
function normalizeUsage(u: Record<string, any>): Record<string, number> {
  const pick = (...keys: string[]): number | undefined => {
    for (const k of keys) {
      if (typeof u[k] === 'number') return u[k];
    }
    return undefined;
  };

  const result: Record<string, number> = {};

  const input = pick(
    'input_tokens',
    'inputTokens',
    'prompt_tokens',
    'promptTokens'
  );
  if (input !== undefined) result.input_tokens = input;

  const output = pick(
    'output_tokens',
    'outputTokens',
    'completion_tokens',
    'completionTokens'
  );
  if (output !== undefined) result.output_tokens = output;

  const total = pick('total_tokens', 'totalTokens');
  if (total !== undefined) result.total_tokens = total;

  return result;
}

// ============================================================================
// WeaveRealtimeTracingAdapter
// ============================================================================

/**
 * Attaches to a RealtimeSession and emits Weave calls for the session
 * lifecycle, each model generation turn, and audio output segments.
 *
 * Instantiate via `instrumentRealtimeSession(session)` rather than directly.
 */
export class WeaveRealtimeTracingAdapter {
  // Session-level Weave call
  private sessionCallId: string | null = null;
  private sessionTraceId: string | null = null;
  private sessionStarted = false;

  // Model name extracted from session.created, used to key summary.usage
  private sessionModel: string | null = null;

  // Per-response Generation calls: responseId → Weave callId
  private generationCalls = new Map<string, string>();

  // Current Audio Out call and which responseId it belongs to
  private audioCallId: string | null = null;
  private audioResponseId: string | null = null;

  constructor(private readonly session: RealtimeSessionLike) {
    this.attachListeners();
  }

  // ---- Listener management ----

  private attachListeners() {
    // Session lifecycle — raw server events forwarded by the session proxy
    this.session.on('transport_event', this.onTransportEvent);
    // Generation and audio lifecycle — semantic transport-layer events
    this.session.transport.on('turn_started', this.onTurnStarted);
    this.session.transport.on('turn_done', this.onTurnDone);
    this.session.transport.on('audio', this.onAudio);
    this.session.transport.on('audio_done', this.onAudioDone);
    // Disconnect detection
    this.session.transport.on('connection_change', this.onConnectionChange);
  }

  /**
   * Remove all listeners and close any open calls.
   * Call this if you need to stop tracing before the session closes naturally.
   */
  detach() {
    this.session.off('transport_event', this.onTransportEvent);
    this.session.transport.off('turn_started', this.onTurnStarted);
    this.session.transport.off('turn_done', this.onTurnDone);
    this.session.transport.off('audio', this.onAudio);
    this.session.transport.off('audio_done', this.onAudioDone);
    this.session.transport.off('connection_change', this.onConnectionChange);
    // Close any calls left open
    this.closeAudioCall({});
    for (const [responseId] of this.generationCalls) {
      this.closeGenerationCall(responseId, {status: 'detached'});
    }
    this.closeSessionCall();
  }

  // ---- Event handlers (arrow functions for stable identity across on/off) ----

  /**
   * Handles raw server-sent events forwarded by the session's transport_event
   * proxy.  Only session lifecycle events are handled here.
   *
   *   session.created  → open Session call
   *   session.updated  → point-in-time Session Update call
   */
  private onTransportEvent = (event: any): void => {
    if (!event?.type) return;

    switch (event.type) {
      case 'session.created':
        this.openSessionCall(event.session ?? {});
        break;
      case 'session.updated':
        this.recordSessionUpdate(event.session ?? {});
        break;
    }
  };

  /**
   * Emitted by the transport when a new response turn begins.
   * Shape: { type: 'response_started', providerData: { response: { id, ... }, ... } }
   * responseId is at event.providerData.response.id
   */
  private onTurnStarted = (event: any): void => {
    const responseId: string | undefined = event?.providerData?.response?.id;
    if (responseId) {
      this.openGenerationCall(responseId);
    }
  };

  /**
   * Emitted by the transport when the model finishes a response turn.
   * Shape: { type: 'response_done', response: { id, output, usage, ... } }
   */
  private onTurnDone = (event: any): void => {
    const responseId: string | undefined = event?.response?.id;
    // Close any Audio Out still open for this response (e.g. interrupted)
    if (responseId && this.audioResponseId === responseId) {
      this.closeAudioCall({});
    }
    if (responseId) {
      this.closeGenerationCall(responseId, event.response ?? {});
    }
  };

  /**
   * Emitted by the transport when audio data arrives from the model.
   * Shape: { type: 'audio', data: ArrayBuffer, responseId: string }
   * Open Audio Out on the first chunk for each responseId.
   */
  private onAudio = (event: any): void => {
    const responseId: string | undefined = event?.responseId;
    if (responseId && this.audioCallId === null) {
      this.openAudioCall(responseId);
    }
  };

  /**
   * Emitted by the transport when audio generation is complete.
   * Shape: [] (no payload)
   */
  private onAudioDone = (): void => {
    this.closeAudioCall({});
  };

  private onConnectionChange = (status: string): void => {
    if (status === 'disconnected') {
      // Close Audio Out and all open Generation calls (e.g. abrupt disconnect)
      this.closeAudioCall({});
      for (const [responseId] of this.generationCalls) {
        this.closeGenerationCall(responseId, {status: 'disconnected'});
      }
      this.closeSessionCall();
    }
  };

  // ---- Weave call helpers ----

  private openSessionCall(sessionData: Record<string, any>) {
    const client = getGlobalClient();
    if (!client || this.sessionStarted) return;
    this.sessionStarted = true;

    const callId = uuidv7();
    const traceId = uuidv7();

    client.saveCallStart({
      project_id: client.projectId,
      id: callId,
      op_name: 'realtime.session',
      display_name: 'Realtime Session',
      trace_id: traceId,
      parent_id: null,
      started_at: new Date().toISOString(),
      inputs: sessionData,
      attributes: {kind: 'agent'},
    });

    this.sessionCallId = callId;
    this.sessionTraceId = traceId;
    this.sessionModel = sessionData.model ?? null;
  }

  private closeSessionCall() {
    const client = getGlobalClient();
    if (!client || !this.sessionCallId) return;

    client.saveCallEnd({
      project_id: client.projectId,
      id: this.sessionCallId,
      ended_at: new Date().toISOString(),
      output: {},
      summary: {},
    });

    this.sessionCallId = null;
    this.sessionTraceId = null;
    this.sessionStarted = false;
  }

  private recordSessionUpdate(sessionData: Record<string, any>) {
    const client = getGlobalClient();
    if (!client || !this.sessionCallId || !this.sessionTraceId) return;

    const callId = uuidv7();
    // Session updates are instantaneous — start and end at the same timestamp
    const now = new Date().toISOString();

    client.saveCallStart({
      project_id: client.projectId,
      id: callId,
      op_name: 'realtime.session.update',
      display_name: 'Realtime Session Update',
      trace_id: this.sessionTraceId,
      parent_id: this.sessionCallId,
      started_at: now,
      inputs: sessionData,
      attributes: {kind: 'agent'},
    });

    client.saveCallEnd({
      project_id: client.projectId,
      id: callId,
      ended_at: now,
      output: sessionData,
      summary: {},
    });
  }

  private openGenerationCall(responseId: string) {
    const client = getGlobalClient();
    if (!client || !this.sessionCallId || !this.sessionTraceId) return;
    // Guard against duplicate starts for the same response
    if (this.generationCalls.has(responseId)) return;

    const callId = uuidv7();

    client.saveCallStart({
      project_id: client.projectId,
      id: callId,
      op_name: 'realtime.generation',
      display_name: 'Generation',
      trace_id: this.sessionTraceId,
      parent_id: this.sessionCallId,
      started_at: new Date().toISOString(),
      inputs: {response_id: responseId},
      attributes: {kind: 'llm'},
    });

    this.generationCalls.set(responseId, callId);
  }

  private closeGenerationCall(
    responseId: string,
    response: Record<string, any>
  ) {
    const client = getGlobalClient();
    const callId = this.generationCalls.get(responseId);
    if (!client || !callId) return;

    const summary: Record<string, any> = {};
    if (response.usage) {
      const modelKey = this.sessionModel ?? 'gpt-4o-realtime';
      summary.usage = {[modelKey]: normalizeUsage(response.usage)};
    }

    client.saveCallEnd({
      project_id: client.projectId,
      id: callId,
      ended_at: new Date().toISOString(),
      output: response,
      summary,
    });

    this.generationCalls.delete(responseId);
  }

  private openAudioCall(responseId: string) {
    const client = getGlobalClient();
    if (!client || !this.sessionTraceId) return;
    // Guard against duplicate audio calls
    if (this.audioCallId) return;

    const parentCallId = this.generationCalls.get(responseId);
    if (!parentCallId) return;

    const callId = uuidv7();

    client.saveCallStart({
      project_id: client.projectId,
      id: callId,
      op_name: 'realtime.audio_output',
      display_name: 'Audio Out',
      trace_id: this.sessionTraceId,
      parent_id: parentCallId,
      started_at: new Date().toISOString(),
      inputs: {},
      attributes: {kind: 'llm'},
    });

    this.audioCallId = callId;
    this.audioResponseId = responseId;
  }

  private closeAudioCall(output: Record<string, any>) {
    const client = getGlobalClient();
    if (!client || !this.audioCallId) return;

    client.saveCallEnd({
      project_id: client.projectId,
      id: this.audioCallId,
      ended_at: new Date().toISOString(),
      output,
      summary: {},
    });

    this.audioCallId = null;
    this.audioResponseId = null;
  }
}

// ============================================================================
// Public API
// ============================================================================

/**
 * Attach Weave tracing to a RealtimeSession instance.
 *
 * Call this immediately after creating the session, before `session.connect()`.
 * Returns the adapter so you can call `.detach()` if needed.
 *
 * @example
 * ```typescript
 * import { instrumentRealtimeSession } from 'weave';
 *
 * const session = new RealtimeSession(agent);
 * instrumentRealtimeSession(session);
 * await session.connect({ apiKey: process.env.OPENAI_API_KEY });
 * ```
 */
export function instrumentRealtimeSession(
  session: any
): WeaveRealtimeTracingAdapter {
  return new WeaveRealtimeTracingAdapter(session as RealtimeSessionLike);
}
