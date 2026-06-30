import {startConversation, startTurn} from '../../genai/api';
import {runIsolated} from '../../genai/context';

import {setupExporterPerTest, setupGenAITestEnvironment} from './common';

// Custom (non-semconv) attributes a host sets once at the root and expects on
// every span -- e.g. weave-openclaw's integration identity.
const CUSTOM = {
  'weave.integration.name': 'weave-openclaw',
  'weave.integration.version': '0.1.1',
};

describe('custom attribute propagation', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

  it('propagates startConversation attributes to every span when each is opened in its own runIsolated frame', () => {
    // Mirrors a decoupled-callback host (the OpenClaw plugin): the Conversation
    // is created once and stored, then each child span is opened later in a
    // fresh runIsolated frame, so ambient state.conversation is null at every
    // create(). The attributes must still ride the stored-handle chain.
    const conversation = runIsolated(() =>
      startConversation({conversationId: 'c-x', attributes: CUSTOM})
    );
    const turn = runIsolated(() =>
      conversation.startTurn({agentName: 'agent', model: 'm'})
    );
    const llm = runIsolated(() => turn.startLLM({model: 'm'}));
    const toolUnderTurn = runIsolated(() =>
      turn.startTool({name: 'search', toolCallId: 't1'})
    );
    const toolUnderLlm = runIsolated(() =>
      llm.startTool({name: 'fetch', toolCallId: 't2'})
    );
    const sub = runIsolated(() => turn.startSubagent({name: 'critic'}));
    toolUnderLlm.end();
    toolUnderTurn.end();
    sub.end();
    llm.end();
    turn.end();
    conversation.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(5); // turn, llm, 2 tools, subagent
    for (const s of spans) {
      expect(s.attributes['weave.integration.name']).toBe('weave-openclaw');
      expect(s.attributes['weave.integration.version']).toBe('0.1.1');
    }
  });

  it('propagates a rootless startTurn({attributes}) to its children (no Conversation)', () => {
    // The sessionless path: no Conversation, attributes set on the root Turn.
    const turn = runIsolated(() =>
      startTurn({agentName: 'agent', model: 'm', attributes: CUSTOM})
    );
    const llm = runIsolated(() => turn.startLLM({model: 'm'}));
    const tool = runIsolated(() =>
      turn.startTool({name: 'search', toolCallId: 't1'})
    );
    tool.end();
    llm.end();
    turn.end();

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(3); // turn, llm, tool
    for (const s of spans) {
      expect(s.attributes['weave.integration.name']).toBe('weave-openclaw');
    }
  });

  it('still propagates attributes in the single-frame usage (one runIsolated)', () => {
    // Regression guard: the SDK's documented single-frame usage keeps working
    // via the ambient state read, unchanged by the handle-threading addition.
    runIsolated(() => {
      const conversation = startConversation({
        conversationId: 'c-1',
        attributes: CUSTOM,
      });
      const turn = conversation.startTurn({agentName: 'agent'});
      const llm = turn.startLLM({model: 'm'});
      const tool = llm.startTool({name: 'search'});
      tool.end();
      llm.end();
      turn.end();
      conversation.end();
    });

    const spans = getExporter().getFinishedSpans();
    expect(spans).toHaveLength(3);
    for (const s of spans) {
      expect(s.attributes['weave.integration.name']).toBe('weave-openclaw');
    }
  });

  it('merges per-turn attributes over conversation attributes', () => {
    const conversation = runIsolated(() =>
      startConversation({conversationId: 'c-1', attributes: {a: 'conv', b: 'conv'}})
    );
    const turn = runIsolated(() =>
      conversation.startTurn({attributes: {b: 'turn', c: 'turn'}})
    );
    const llm = runIsolated(() => turn.startLLM({model: 'm'}));
    llm.end();
    turn.end();
    conversation.end();

    for (const s of getExporter().getFinishedSpans()) {
      expect(s.attributes['a']).toBe('conv'); // conversation-only
      expect(s.attributes['b']).toBe('turn'); // per-turn overrides
      expect(s.attributes['c']).toBe('turn'); // per-turn-only
    }
  });
});
