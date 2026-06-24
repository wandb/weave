import {EventEmitter} from 'events';
import {getGlobalClient} from '../../clientApi';
import {
  WeaveRealtimeTracingAdapter,
  type WeaveRealtimeTracingAdapterOptions,
} from '../../integrations/openai.realtime.agent';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';
import {initWithCustomTraceServer} from '../clientMock';

function makeMockSession() {
  const session = new EventEmitter() as any;
  session.transport = new EventEmitter();
  return session;
}

// Under calls_complete, an open span is held client-side until it pairs with
// its end; flushing ships unpaired starts/ends so the server sees them.
async function flush() {
  const client = getGlobalClient();
  if (!client) {
    throw new Error('global client not initialized');
  }
  await client.waitForBatchProcessing();
}

function createAdapter(options?: WeaveRealtimeTracingAdapterOptions) {
  const session = makeMockSession();
  const adapter = new WeaveRealtimeTracingAdapter(session, options);
  return {session, adapter};
}

describe('WeaveRealtimeTracingAdapter', () => {
  let inMemoryTraceServer: InMemoryTraceServer;
  const testProjectName = 'test-project';

  beforeEach(() => {
    inMemoryTraceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(testProjectName, inMemoryTraceServer);
  });

  test('session.created opens a session call', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {
      type: 'session.created',
      session: {model: 'gpt-4o-realtime'},
    });

    await flush();
    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toBe('realtime.session');
    expect(calls[0].display_name).toBe('Realtime Session');
    expect(calls[0].parent_id).toBeNull();
    expect(calls[0].ended_at).toBeUndefined();

    // Integration-tracking metadata is stamped on calls this adapter
    // produces. Match by name rather than by index, since a realtime trace
    // can contain other calls.
    const stamped = calls.map(c => c.attributes.integration).filter(Boolean);
    const mine = stamped.filter(i => i.name === 'openai_agents_realtime');
    expect(mine.length).toBeGreaterThan(0);
    expect(
      mine.every(i => i.meta?.package_name === '@openai/agents-realtime')
    ).toBe(true);
  });

  test('default session root is held pending, visible only after flush', async () => {
    const requestSpy = jest.spyOn(inMemoryTraceServer, 'request');
    const {session} = createAdapter();
    session.emit('transport_event', {
      type: 'session.created',
      session: {model: 'gpt-4o-realtime'},
    });

    // No eager start: nothing reaches the server until the session pairs/flushes.
    expect(requestSpy).not.toHaveBeenCalled();
    await flush();
    expect(
      requestSpy.mock.calls.some(([p]) =>
        (p as {path: string}).path.endsWith('/call/start')
      )
    ).toBe(true);
  });

  test('eagerSessionRoot sends the root start immediately, before close', async () => {
    const requestSpy = jest.spyOn(inMemoryTraceServer, 'request');
    const {session} = createAdapter({eagerSessionRoot: true});
    session.emit('transport_event', {
      type: 'session.created',
      session: {model: 'gpt-4o-realtime'},
    });
    await getGlobalClient()!.waitForBatchProcessing();

    // The root is visible while still open, sent via the eager v2 start endpoint.
    const startPaths = requestSpy.mock.calls
      .map(([p]) => (p as {path: string}).path)
      .filter(path => path.endsWith('/call/start'));
    expect(startPaths).toHaveLength(1);
    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(calls).toHaveLength(1);
    expect(calls[0].op_name).toBe('realtime.session');
    expect(calls[0].ended_at).toBeUndefined();
  });

  test('session.updated records an instantaneous session update call', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.emit('transport_event', {
      type: 'session.updated',
      session: {voice: 'alloy'},
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    const updateCall = calls.find(c => c.op_name === 'realtime.session.update');
    expect(updateCall).toBeDefined();
    expect(updateCall!.display_name).toBe('Realtime Session Update');
    expect(updateCall!.ended_at).toBeDefined();
  });

  test('history_added with input_text records a User Message call', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.emit('history_added', {
      type: 'message',
      role: 'user',
      content: [{type: 'input_text', text: 'hello world'}],
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    const msgCall = calls.find(c => c.op_name === 'realtime.user_message');
    expect(msgCall).toBeDefined();
    expect(msgCall!.display_name).toBe('User Message');
    expect(msgCall!.inputs).toMatchObject({text: 'hello world'});
    expect(msgCall!.ended_at).toBeDefined();
  });

  test('history_added with input_audio opens a voice input call; history_updated closes it with transcript', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.emit('history_added', {
      type: 'message',
      role: 'user',
      itemId: 'item-voice-1',
      content: [{type: 'input_audio'}],
    });

    // Call should be open (no ended_at yet)
    await flush();
    let calls = await inMemoryTraceServer.getCalls(testProjectName);
    const voiceCall = calls.find(c => c.op_name === 'realtime.voice_input');
    expect(voiceCall).toBeDefined();
    expect(voiceCall!.ended_at).toBeUndefined();

    // Finalize the voice turn
    session.emit('history_updated', [
      {
        itemId: 'item-voice-1',
        status: 'completed',
        content: [{type: 'input_audio', transcript: 'turn the lights on'}],
      },
    ]);

    await flush();
    calls = await inMemoryTraceServer.getCalls(testProjectName);
    const closedCall = calls.find(c => c.op_name === 'realtime.voice_input');
    expect(closedCall!.ended_at).toBeDefined();
    expect(closedCall!.output).toMatchObject({
      transcript: 'turn the lights on',
    });
  });

  test('turn_started opens a generation call; turn_done closes it', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    await flush();
    let calls = await inMemoryTraceServer.getCalls(testProjectName);
    const genCall = calls.find(c => c.op_name === 'realtime.generation');
    expect(genCall).toBeDefined();
    expect(genCall!.ended_at).toBeUndefined();

    session.transport.emit('turn_done', {response: {id: 'resp-1'}});

    await flush();
    calls = await inMemoryTraceServer.getCalls(testProjectName);
    expect(
      calls.find(c => c.op_name === 'realtime.generation')!.ended_at
    ).toBeDefined();
  });

  test('audio events open an Audio Out call nested under the generation', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });
    session.transport.emit('audio', {
      responseId: 'resp-1',
      data: new ArrayBuffer(8),
    });
    session.transport.emit('audio_done');

    await flush();
    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    const genCall = calls.find(c => c.op_name === 'realtime.generation');
    const audioCall = calls.find(c => c.op_name === 'realtime.audio_output');
    expect(audioCall).toBeDefined();
    expect(audioCall!.parent_id).toBe(genCall!.id);
    expect(audioCall!.ended_at).toBeDefined();
  });

  test('agent_tool_start and agent_tool_end create a tool call', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.emit(
      'agent_tool_start',
      null,
      null,
      {name: 'get_weather'},
      {toolCall: {callId: 'tc-1', arguments: '{"city":"NYC"}'}}
    );
    session.emit('agent_tool_end', null, null, null, 'sunny', {
      toolCall: {callId: 'tc-1'},
    });

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    const toolCall = calls.find(c => c.op_name === 'realtime.tool.get_weather');
    expect(toolCall).toBeDefined();
    expect(toolCall!.display_name).toBe('get_weather');
    expect(toolCall!.inputs).toMatchObject({city: 'NYC'});
    expect(toolCall!.output).toMatchObject({result: 'sunny'});
    expect(toolCall!.ended_at).toBeDefined();
  });

  test('disconnection closes all open calls', async () => {
    const {session} = createAdapter();
    session.emit('transport_event', {type: 'session.created', session: {}});
    session.transport.emit('turn_started', {
      providerData: {response: {id: 'resp-1'}},
    });

    session.transport.emit('connection_change', 'disconnected');

    const calls = await inMemoryTraceServer.getCalls(testProjectName);
    for (const call of calls) {
      expect(call.ended_at).toBeDefined();
    }
  });
});
