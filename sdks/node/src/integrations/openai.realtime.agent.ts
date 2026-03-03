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
 *   ├── Tool Call: <name>            (on agent_tool_start → agent_tool_end)
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
 * Wrap raw PCM16 mono audio into a WAV container.
 * The OpenAI Realtime API streams 24 kHz, 16-bit, mono PCM.
 */
function pcmToWav(pcm: Buffer): Buffer {
  const channels = 1;
  const sampleRate = 24000;
  const bitDepth = 16;
  const wav = Buffer.alloc(44 + pcm.length);
  wav.write('RIFF', 0);
  wav.writeUInt32LE(36 + pcm.length, 4);
  wav.write('WAVE', 8);
  wav.write('fmt ', 12);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20); // PCM
  wav.writeUInt16LE(channels, 22);
  wav.writeUInt32LE(sampleRate, 24);
  wav.writeUInt32LE(sampleRate * channels * (bitDepth / 8), 28);
  wav.writeUInt16LE(channels * (bitDepth / 8), 32);
  wav.writeUInt16LE(bitDepth, 34);
  wav.write('data', 36);
  wav.writeUInt32LE(pcm.length, 40);
  wav.set(pcm, 44); // Uint8Array.set — accepts ArrayLike<number>, no Buffer-copy type issues
  return wav;
}

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
  // Accumulated PCM chunks per responseId — assembled into WAV on close
  private audioChunks = new Map<string, Buffer[]>();

  // In-flight tool calls: toolCallId → Weave callId
  private toolCalls = new Map<string, string>();

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
    // Tool calls
    this.session.on('agent_tool_start', this.onToolStart);
    this.session.on('agent_tool_end', this.onToolEnd);
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
    this.session.off('agent_tool_start', this.onToolStart);
    this.session.off('agent_tool_end', this.onToolEnd);
    // Close any calls left open
    this.audioChunks.clear();
    this.closeAudioCall({});
    for (const [responseId] of this.generationCalls) {
      this.closeGenerationCall(responseId, {status: 'detached'});
    }
    for (const [toolCallId] of this.toolCalls) {
      this.closeToolCall(toolCallId, {status: 'detached'});
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
    if (!responseId) return;
    // Accumulate raw PCM chunks
    const chunks = this.audioChunks.get(responseId) ?? [];
    chunks.push(Buffer.from(event.data as ArrayBuffer));
    this.audioChunks.set(responseId, chunks);
    // Open the Audio Out call on the first chunk
    if (this.audioCallId === null) {
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
      this.audioChunks.clear();
      this.closeAudioCall({});
      for (const [responseId] of this.generationCalls) {
        this.closeGenerationCall(responseId, {status: 'disconnected'});
      }
      for (const [toolCallId] of this.toolCalls) {
        this.closeToolCall(toolCallId, {status: 'disconnected'});
      }
      this.closeSessionCall();
    }
  };

  /**
   * Emitted by the session when the agent begins executing a tool call.
   * Shape: (context, agent, tool, details) where details.toolCall.callId is the correlation key.
   */
  private onToolStart = (
    _ctx: any,
    _agent: any,
    tool: any,
    details: any
  ): void => {
    const callId: string | undefined = details?.toolCall?.callId;
    const toolName: string | undefined = tool?.name;
    if (!callId || !toolName) return;

    let inputs: Record<string, any> = {};
    try {
      inputs = JSON.parse(details.toolCall.arguments ?? '{}');
    } catch {
      inputs = {arguments: details.toolCall.arguments};
    }

    this.openToolCall(callId, toolName, inputs);
  };

  /**
   * Emitted by the session when a tool call completes.
   * Shape: (context, agent, tool, result, details) where result is the string output.
   */
  private onToolEnd = (
    _ctx: any,
    _agent: any,
    _tool: any,
    result: string,
    details: any
  ): void => {
    const callId: string | undefined = details?.toolCall?.callId;
    if (!callId) return;
    this.closeToolCall(callId, {result});
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

    // Snapshot and clear state immediately so re-entrant calls are safe
    const callId = this.audioCallId;
    const responseId = this.audioResponseId;
    const endedAt = new Date().toISOString();
    this.audioCallId = null;
    this.audioResponseId = null;

    const chunks = responseId ? this.audioChunks.get(responseId) : undefined;
    if (responseId) this.audioChunks.delete(responseId);

    (async () => {
      let finalOutput = output;
      if (chunks && chunks.length > 0) {
        try {
          const pcm = Buffer.concat(chunks as unknown as Uint8Array[]);
          const audioRef = await client.serializeAudio(pcmToWav(pcm));
          finalOutput = {...output, audio: audioRef};
        } catch {
          // fall through with original output
        }
      }
      client.saveCallEnd({
        project_id: client.projectId,
        id: callId,
        ended_at: endedAt,
        output: finalOutput,
        summary: {},
      });
    })();
  }

  private openToolCall(
    toolCallId: string,
    toolName: string,
    inputs: Record<string, any>
  ) {
    const client = getGlobalClient();
    if (!client || !this.sessionCallId || !this.sessionTraceId) return;
    if (this.toolCalls.has(toolCallId)) return;

    const callId = uuidv7();

    client.saveCallStart({
      project_id: client.projectId,
      id: callId,
      op_name: `realtime.tool.${toolName}`,
      display_name: toolName,
      trace_id: this.sessionTraceId,
      parent_id: this.sessionCallId,
      started_at: new Date().toISOString(),
      inputs,
      attributes: {kind: 'tool'},
    });

    this.toolCalls.set(toolCallId, callId);
  }

  private closeToolCall(toolCallId: string, output: Record<string, any>) {
    const client = getGlobalClient();
    const callId = this.toolCalls.get(toolCallId);
    if (!client || !callId) return;

    client.saveCallEnd({
      project_id: client.projectId,
      id: callId,
      ended_at: new Date().toISOString(),
      output,
      summary: {},
    });

    this.toolCalls.delete(toolCallId);
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
