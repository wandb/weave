import {fixturePath, genProjectId, getCalls, launchAppFrom} from './utils';

interface Call {
  id?: string;
  op_name?: string;
  parent_id?: string | null;
  trace_id?: string;
  display_name?: string;
  exception?: string | null;
  attributes?: {kind?: string; integration?: {name?: string}};
  output?: Record<string, unknown>;
  summary?: {usage?: Record<string, Record<string, unknown>>};
}

describe('hostApps — claude-agent-sdk', () => {
  test('auto-instruments the real @anthropic-ai/claude-agent-sdk query() and emits a full trace tree', async () => {
    const projectId = genProjectId();
    const result = await launchAppFrom({
      path: fixturePath('claude-agent-sdk'),
      projectId,
    });
    if (result.exitCode !== 0) {
      throw new Error(
        `claude-agent-sdk fixture exited ${result.exitCode}\n` +
          `stdout:\n${result.stdout}\nstderr:\n${result.stderr}`
      );
    }

    const calls = (await getCalls(projectId)) as Call[];

    // Root agent call, stamped with this integration's provenance.
    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query');
    expect(root).toBeDefined();
    expect(root!.parent_id).toBeFalsy();
    expect(root!.attributes?.kind).toBe('agent');
    expect(root!.attributes?.integration?.name).toBe('claude_agent_sdk');
    expect(root!.exception).toBeFalsy();
    expect(root!.output?.status).toBe('completed');
    expect(root!.output?.result).toBe('There are two files.');

    // Child calls, created from the streamed messages, all under the root.
    const children = calls.filter(c => c.parent_id === root!.id);
    const byOp = (op: string) => children.filter(c => c.op_name === op);

    const thinking = byOp('claude_agent_sdk.thinking');
    expect(thinking).toHaveLength(1);
    expect(thinking[0].attributes?.kind).toBe('llm');
    expect(thinking[0].output).toMatchObject({
      thinking: 'I should list the files.',
    });

    // Two assistant text turns → two text children.
    const text = byOp('claude_agent_sdk.text');
    expect(text).toHaveLength(2);
    expect(text.every(c => c.attributes?.kind === 'llm')).toBe(true);

    const tool = byOp('claude_agent_sdk.tool_use.Bash');
    expect(tool).toHaveLength(1);
    expect(tool[0].attributes?.kind).toBe('tool');
    expect(tool[0].display_name).toBe('Bash(command="ls")');
    // Finished by the matching tool_result (the user message), not left open.
    expect(tool[0].output).toMatchObject({
      tool_use_id: 'tool-1',
      content: 'main.mjs\npackage.json',
    });

    // Per-model usage lifted onto the root, mapped to Weave's snake_case keys
    // (the camelCase ModelUsage shape must not leak through).
    const usage = root!.summary?.usage?.['claude-fake'];
    expect(usage).toMatchObject({
      requests: 1,
      input_tokens: 8,
      output_tokens: 12,
    });
    expect((usage as Record<string, unknown>).inputTokens).toBeUndefined();

    // The whole tree shares the root's trace.
    expect(calls.every(c => c.trace_id === root!.trace_id)).toBe(true);
  }, 60_000);
});
