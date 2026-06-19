import {randomUUID} from 'crypto';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

import {fixturePath, genProjectId, launchAppFrom} from './utils';

interface CapturedSpan {
  name: string;
  spanId: string;
  parentSpanId?: string;
  traceId: string;
  attributes: Record<string, unknown>;
  statusCode: number;
}

describe('hostApps — claude-agent-sdk', () => {
  test('auto-instruments the real @anthropic-ai/claude-agent-sdk query() and emits a GenAI agent span tree', async () => {
    const projectId = genProjectId();
    // The fixture writes its captured OTel spans here (it installs a capturing
    // span processor via weave.init), so we assert the real emission path
    // without standing up an OTLP receiver.
    const spanFile = path.join(os.tmpdir(), `cas-otel-${randomUUID()}.json`);

    const result = await launchAppFrom({
      path: fixturePath('claude-agent-sdk'),
      projectId,
      extraEnv: {SPAN_OUTPUT_FILE: spanFile},
    });
    if (result.exitCode !== 0) {
      throw new Error(
        `claude-agent-sdk fixture exited ${result.exitCode}\n` +
          `stdout:\n${result.stdout}\nstderr:\n${result.stderr}`
      );
    }

    const spans = JSON.parse(
      fs.readFileSync(spanFile, 'utf8')
    ) as CapturedSpan[];
    fs.rmSync(spanFile, {force: true});

    const findSpan = (name: string): CapturedSpan => {
      const span = spans.find(s => s.name === name);
      if (!span) {
        throw new Error(
          `no span named '${name}' (saw: ${spans.map(s => s.name).join(', ')})`
        );
      }
      return span;
    };

    // Root invoke_agent span, stamped with this integration's provenance.
    const invoke = findSpan('invoke_agent claude_agent_sdk');
    expect(invoke.parentSpanId).toBeFalsy();
    expect(invoke.attributes['gen_ai.operation.name']).toBe('invoke_agent');
    expect(invoke.attributes['gen_ai.agent.name']).toBe('claude_agent_sdk');
    expect(invoke.attributes['integration.name']).toBe('claude_agent_sdk');
    // The fake CLI reports a session_id; it becomes the conversation id.
    const conversationId = invoke.attributes['gen_ai.conversation.id'];
    expect(conversationId).toBe('fake-session');
    // Usage from the result message is lifted onto the root.
    expect(invoke.attributes['gen_ai.usage.input_tokens']).toBe(8);
    expect(invoke.attributes['gen_ai.usage.output_tokens']).toBe(12);

    // chat spans (one per assistant message) and the tool span hang off the
    // root and share its trace + conversation id.
    const chats = spans.filter(s => s.name === 'chat claude-fake');
    expect(chats.length).toBeGreaterThanOrEqual(1);
    expect(chats.every(c => c.parentSpanId === invoke.spanId)).toBe(true);

    const tool = findSpan('execute_tool Bash');
    expect(tool.attributes['gen_ai.operation.name']).toBe('execute_tool');
    expect(tool.attributes['gen_ai.tool.name']).toBe('Bash');
    expect(tool.attributes['gen_ai.tool.call.result']).toBe(
      'main.mjs\npackage.json'
    );
    expect(tool.parentSpanId).toBe(invoke.spanId);

    for (const span of spans) {
      expect(span.traceId).toBe(invoke.traceId);
      expect(span.attributes['gen_ai.conversation.id']).toBe(conversationId);
    }
  }, 60_000);
});
