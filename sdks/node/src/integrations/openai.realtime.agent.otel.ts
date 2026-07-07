/**
 * OTel GenAI export for the OpenAI Realtime integration.
 *
 * Mirrors the Python ``OTelStateExporter``: listens to the same
 * ``RealtimeSession`` events as the legacy ``WeaveRealtimeTracingAdapter``
 * but emits OpenTelemetry GenAI spans instead of Weave calls.
 *
 * The realtime API is speech-to-speech, so each turn maps to one ``chat``
 * span:
 *
 *   invoke_agent openai_realtime     # session root; ended on disconnect
 *   ├── chat {model}                 # one per turn_done
 *   │   └── execute_tool {name}      # one per function_call output item
 *   ├── chat {model}
 *   └── chat {model}
 *
 * Selected when ``settings.useOTelV2 === true`` (the default), matching the
 * Python SDK's ``should_use_otel_v2()`` gate.
 */

import {
  type Context as OtelContext,
  type Span as OtelSpan,
  ROOT_CONTEXT,
  SpanKind,
  SpanStatusCode,
  trace as otelTrace,
} from '@opentelemetry/api';

import {getWeaveTracer} from '../genai/provider';
import {
  ATTR_GEN_AI_AGENT_NAME,
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OPERATION_NAME,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_TYPE,
  ATTR_GEN_AI_PROVIDER_NAME,
  ATTR_GEN_AI_REQUEST_MAX_TOKENS,
  ATTR_GEN_AI_REQUEST_MODEL,
  ATTR_GEN_AI_REQUEST_TEMPERATURE,
  ATTR_GEN_AI_RESPONSE_ID,
  ATTR_GEN_AI_RESPONSE_MODEL,
  ATTR_GEN_AI_TOOL_CALL_ARGUMENTS,
  ATTR_GEN_AI_TOOL_CALL_ID,
  ATTR_GEN_AI_TOOL_NAME,
  ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
  ATTR_GEN_AI_USAGE_OUTPUT_TOKENS,
} from '../genai/semconv';
import {asOtelAttributes, libraryIntegration} from './integrationMetadata';
import type {RealtimeSession} from '@openai/agents-realtime';
import type {Message, MessagePart} from '../genai/types';

const TRACER_NAME = 'weave.openai_realtime';
const DEFAULT_AGENT_NAME = 'openai_realtime';
const PROVIDER_NAME = 'openai';

const INTEGRATION_OTEL_ATTRS = asOtelAttributes(
  libraryIntegration('openai_agents_realtime', {
    packageName: '@openai/agents-realtime',
  })
);

const TEXT_CONTENT_TYPES = new Set(['text', 'input_text', 'output_text']);
const AUDIO_CONTENT_TYPES = new Set(['audio', 'output_audio']);

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
  wav.set(pcm, 44);
  return wav;
}

export class WeaveRealtimeOTelAdapter {
  private rootSpan: OtelSpan | null = null;
  private rootContext: OtelContext | null = null;

  private sessionModel = '';
  private sessionId = '';
  private sessionConfig: Record<string, any> = {};

  private turnStartTimes = new Map<string, number>();

  private audioChunks = new Map<string, Buffer[]>();
  private pendingAudioChunks: Buffer[] = [];
  private audioInputChunks = new Map<string, Buffer[]>();

  private inputItems: Array<{role: string; parts: MessagePart[]}> = [];

  private lastActivityTime: number | null = null;

  constructor(private readonly session: RealtimeSession) {
    this.attachListeners();
  }

  // ---- Listener management ----

  private attachListeners() {
    this.session.on('transport_event', this.onTransportEvent);
    this.session.transport.on('turn_started', this.onTurnStarted);
    this.session.transport.on('turn_done', this.onTurnDone);
    this.session.transport.on('audio', this.onAudio);
    this.session.transport.on('audio_done', this.onAudioDone);
    this.session.transport.on('connection_change', this.onConnectionChange);
    this.session.on('history_added', this.onHistoryAdded);
    this.session.on('history_updated', this.onHistoryUpdated);
  }

  detach() {
    this.session.off('transport_event', this.onTransportEvent);
    this.session.transport.off('turn_started', this.onTurnStarted);
    this.session.transport.off('turn_done', this.onTurnDone);
    this.session.transport.off('audio', this.onAudio);
    this.session.transport.off('audio_done', this.onAudioDone);
    this.session.transport.off('connection_change', this.onConnectionChange);
    this.session.off('history_added', this.onHistoryAdded);
    this.session.off('history_updated', this.onHistoryUpdated);
    this.audioChunks.clear();
    this.pendingAudioChunks = [];
    this.audioInputChunks.clear();
    this.endRootSpan();
  }

  public pushAudioChunk(audio: ArrayBuffer): void {
    this.pendingAudioChunks.push(Buffer.from(audio));
  }

  // ---- Event handlers (arrow functions for stable on/off identity) ----

  private onTransportEvent = (event: any): void => {
    if (!event?.type) return;
    switch (event.type) {
      case 'session.created':
      case 'session.updated':
        this.storeSession(event.session ?? {});
        break;
      case 'input_audio_buffer.committed': {
        const itemId: string | undefined = event.item_id;
        if (itemId && this.pendingAudioChunks.length > 0) {
          this.audioInputChunks.set(itemId, this.pendingAudioChunks.splice(0));
        } else {
          this.pendingAudioChunks = [];
        }
        break;
      }
      case 'input_audio_buffer.cleared':
        this.pendingAudioChunks = [];
        break;
    }
  };

  private onTurnStarted = (event: any): void => {
    const responseId: string | undefined = event?.providerData?.response?.id;
    if (responseId) {
      this.turnStartTimes.set(responseId, Date.now());
    }
  };

  private onTurnDone = (event: any): void => {
    const response = event?.response;
    if (!response?.id) return;
    const responseId: string = response.id;
    const outputChunks = this.audioChunks.get(responseId);
    this.audioChunks.delete(responseId);
    try {
      this.emitChatSpan(response, outputChunks);
    } catch {
      // Never let span creation break the event flow.
    }
    this.lastActivityTime = Date.now();
  };

  private onAudio = (event: any): void => {
    const responseId: string | undefined = event?.responseId;
    if (!responseId) return;
    const chunks = this.audioChunks.get(responseId) ?? [];
    chunks.push(Buffer.from(event.data as ArrayBuffer));
    this.audioChunks.set(responseId, chunks);
  };

  private onAudioDone = (): void => {
    // Chunks are consumed by emitChatSpan when the turn completes.
  };

  private onConnectionChange = (status: string): void => {
    if (status === 'disconnected') {
      this.audioChunks.clear();
      this.pendingAudioChunks = [];
      this.audioInputChunks.clear();
      this.endRootSpan();
    }
  };

  private onHistoryAdded = (item: any): void => {
    if (item?.type !== 'message' || item?.role !== 'user') return;
    const content: any[] = item.content ?? [];
    const parts: MessagePart[] = [];
    for (const c of content) {
      if (c.type === 'input_text' && c.text) {
        parts.push({type: 'text', content: c.text});
      }
    }
    if (parts.length > 0) {
      this.inputItems.push({role: 'user', parts});
    }
  };

  private onHistoryUpdated = (history: any[]): void => {
    for (const item of history) {
      if (item?.type !== 'message' || item?.role !== 'user') continue;
      if (item.status !== 'completed') continue;
      const transcripts = (item.content ?? [])
        .filter((c: any) => c.type === 'input_audio' && c.transcript)
        .map((c: any) => c.transcript as string);
      if (transcripts.length > 0) {
        this.inputItems.push({
          role: 'user',
          parts: transcripts.map(
            (t: string): MessagePart => ({type: 'text', content: t})
          ),
        });
      }
    }
  };

  // ---- Session state ----

  private storeSession(session: Record<string, any>) {
    this.sessionConfig = session;
    this.sessionModel = session.model ?? this.sessionModel;
    this.sessionId = session.id ?? this.sessionId;
  }

  // ---- Root span (invoke_agent) ----

  private ensureRootSpan(): {span: OtelSpan; context: OtelContext} | null {
    if (this.rootSpan && this.rootContext) {
      return {span: this.rootSpan, context: this.rootContext};
    }

    const tracer = getWeaveTracer(TRACER_NAME);
    const conversationId = this.sessionId;

    const attrs: Record<string, any> = {
      [ATTR_GEN_AI_OPERATION_NAME]: 'invoke_agent',
      [ATTR_GEN_AI_AGENT_NAME]: DEFAULT_AGENT_NAME,
      [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
      ...INTEGRATION_OTEL_ATTRS,
    };
    if (this.sessionModel) {
      attrs[ATTR_GEN_AI_REQUEST_MODEL] = this.sessionModel;
    }
    if (conversationId) {
      attrs[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
    }

    const span = tracer.startSpan(
      `invoke_agent ${DEFAULT_AGENT_NAME}`,
      {kind: SpanKind.CLIENT, attributes: attrs},
      ROOT_CONTEXT
    );
    const context = otelTrace.setSpan(ROOT_CONTEXT, span);
    this.rootSpan = span;
    this.rootContext = context;
    return {span, context};
  }

  private endRootSpan() {
    if (!this.rootSpan) return;
    this.rootSpan.end(this.lastActivityTime ?? undefined);
    this.rootSpan = null;
    this.rootContext = null;
  }

  // ---- Chat span emission ----

  private emitChatSpan(
    response: Record<string, any>,
    outputAudioChunks?: Buffer[]
  ) {
    const root = this.ensureRootSpan();
    if (!root) return;

    const tracer = getWeaveTracer(TRACER_NAME);
    const responseId: string = response.id ?? '';
    const model = this.sessionModel || 'unknown';
    const conversationId = response.conversation_id ?? this.sessionId ?? '';

    const startTime = this.turnStartTimes.get(responseId);
    this.turnStartTimes.delete(responseId);

    const inputMessages = this.buildInputMessages();
    const {outputMessages, toolCallItems, hasAudio} =
      this.buildOutputMessages(response);

    if (hasAudio && outputAudioChunks && outputAudioChunks.length > 0) {
      try {
        const pcm = Buffer.concat(outputAudioChunks);
        const wav = pcmToWav(pcm);
        const assistantMsg = outputMessages[0];
        if (assistantMsg) {
          assistantMsg.parts = assistantMsg.parts ?? [];
          (assistantMsg.parts as any[]).push({
            type: 'uri',
            uri: `data:audio/wav;base64,${wav.toString('base64')}`,
            mime_type: 'audio/wav',
            modality: 'audio',
          });
        }
      } catch {
        // Fall through with transcript only
      }
    }

    const attrs: Record<string, any> = {
      [ATTR_GEN_AI_OPERATION_NAME]: 'chat',
      [ATTR_GEN_AI_REQUEST_MODEL]: model,
      [ATTR_GEN_AI_RESPONSE_MODEL]: model,
      [ATTR_GEN_AI_PROVIDER_NAME]: PROVIDER_NAME,
      [ATTR_GEN_AI_RESPONSE_ID]: responseId,
      [ATTR_GEN_AI_OUTPUT_TYPE]: hasAudio ? 'speech' : 'text',
      ...INTEGRATION_OTEL_ATTRS,
    };
    if (conversationId) {
      attrs[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
    }
    if (inputMessages.length > 0) {
      attrs[ATTR_GEN_AI_INPUT_MESSAGES] = JSON.stringify(inputMessages);
    }
    if (outputMessages.length > 0) {
      attrs[ATTR_GEN_AI_OUTPUT_MESSAGES] = JSON.stringify(outputMessages);
    }

    const usage = response.usage;
    if (usage) {
      if (typeof usage.input_tokens === 'number') {
        attrs[ATTR_GEN_AI_USAGE_INPUT_TOKENS] = usage.input_tokens;
      }
      if (typeof usage.output_tokens === 'number') {
        attrs[ATTR_GEN_AI_USAGE_OUTPUT_TOKENS] = usage.output_tokens;
      }
      const inputDetails = usage.input_token_details;
      if (
        typeof inputDetails === 'object' &&
        inputDetails !== null &&
        typeof inputDetails.cached_tokens === 'number'
      ) {
        attrs[ATTR_GEN_AI_USAGE_CACHE_READ_INPUT_TOKENS] =
          inputDetails.cached_tokens;
      }
    }

    if (typeof this.sessionConfig.temperature === 'number') {
      attrs[ATTR_GEN_AI_REQUEST_TEMPERATURE] = this.sessionConfig.temperature;
    }
    if (this.sessionConfig.max_response_output_tokens !== undefined) {
      const maxTokens = Number(this.sessionConfig.max_response_output_tokens);
      if (Number.isFinite(maxTokens)) {
        attrs[ATTR_GEN_AI_REQUEST_MAX_TOKENS] = maxTokens;
      }
    }

    const chatSpan = tracer.startSpan(
      `chat ${model}`.trimEnd(),
      {kind: SpanKind.CLIENT, attributes: attrs, startTime},
      root.context
    );

    const chatContext = otelTrace.setSpan(root.context, chatSpan);
    for (const fc of toolCallItems) {
      this.emitToolSpan(tracer, chatContext, fc, conversationId, startTime);
    }

    if (response.status === 'failed') {
      const details = response.status_details;
      const err =
        typeof details === 'object' && details !== null
          ? details.error
          : undefined;
      const message =
        typeof err === 'object' && err !== null
          ? (err.message ?? 'response failed')
          : 'response failed';
      chatSpan.setStatus({
        code: SpanStatusCode.ERROR,
        message: String(message),
      });
    }

    chatSpan.end();
  }

  // ---- Tool span emission ----

  private emitToolSpan(
    tracer: ReturnType<typeof getWeaveTracer>,
    parentContext: OtelContext,
    fc: Record<string, any>,
    conversationId: string,
    startTime: number | undefined
  ) {
    const name: string = fc.name ?? '';
    const callId: string = fc.call_id ?? fc.id ?? '';
    const args: string =
      typeof fc.arguments === 'string'
        ? fc.arguments
        : JSON.stringify(fc.arguments ?? {});

    const attrs: Record<string, any> = {
      [ATTR_GEN_AI_OPERATION_NAME]: 'execute_tool',
      [ATTR_GEN_AI_TOOL_NAME]: name,
      ...INTEGRATION_OTEL_ATTRS,
    };
    if (callId) {
      attrs[ATTR_GEN_AI_TOOL_CALL_ID] = callId;
    }
    if (args) {
      attrs[ATTR_GEN_AI_TOOL_CALL_ARGUMENTS] = args;
    }
    if (conversationId) {
      attrs[ATTR_GEN_AI_CONVERSATION_ID] = conversationId;
    }

    const toolSpan = tracer.startSpan(
      `execute_tool ${name}`.trimEnd(),
      {kind: SpanKind.INTERNAL, attributes: attrs, startTime},
      parentContext
    );
    toolSpan.end();
  }

  // ---- Message construction ----

  private buildInputMessages(): Message[] {
    return this.inputItems.map(item => ({
      role: item.role as Message['role'],
      parts: [...item.parts],
    }));
  }

  private buildOutputMessages(response: Record<string, any>): {
    outputMessages: Message[];
    toolCallItems: Record<string, any>[];
    hasAudio: boolean;
  } {
    const parts: MessagePart[] = [];
    const toolCallItems: Record<string, any>[] = [];
    let hasAudio = false;

    for (const item of response.output ?? []) {
      if (item.type === 'message') {
        for (const content of item.content ?? []) {
          if (TEXT_CONTENT_TYPES.has(content.type) && content.text) {
            parts.push({type: 'text', content: content.text});
          } else if (AUDIO_CONTENT_TYPES.has(content.type)) {
            hasAudio = true;
            if (content.transcript) {
              parts.push({type: 'text', content: content.transcript});
            }
          }
        }
      } else if (item.type === 'function_call') {
        const callId = item.call_id ?? item.id ?? '';
        const fnName = item.name ?? '';
        const args =
          typeof item.arguments === 'string'
            ? item.arguments
            : JSON.stringify(item.arguments ?? {});
        parts.push({
          type: 'tool_call',
          toolCallId: callId,
          toolName: fnName,
          arguments: args,
        });
        toolCallItems.push(item);
      }
    }

    const outputMessages: Message[] =
      parts.length > 0 ? [{role: 'assistant', parts}] : [];

    return {outputMessages, toolCallItems, hasAudio};
  }
}
