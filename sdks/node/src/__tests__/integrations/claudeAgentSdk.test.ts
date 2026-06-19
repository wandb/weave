import {requireGlobalClient, setGlobalClient} from '../../clientApi';
import {ClaudeAgentTracer} from '../../integrations/claude-agent-sdk/tracer';
import {patchClaudeAgentSdk} from '../../integrations/claudeAgentSdk';
import {
  serializeMessage,
  textDisplayName,
  thinkingDisplayName,
  toolUseDisplayName,
  toWeaveUsage,
  turnDisplayName,
} from '../../integrations/claude-agent-sdk/messages';
import {initWithCustomTraceServer} from '../clientMock';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';

describe('Claude Agent SDK — display names', () => {
  test('tool_use display name formats built-in tools as name(params)', () => {
    expect(toolUseDisplayName('Bash', {command: 'ls'})).toBe(
      'Bash(command="ls")'
    );
  });

  test('tool_use display name formats MCP tools as "Server MCP: Tool(params)"', () => {
    expect(toolUseDisplayName('mcp__math__add', {a: 3, b: 7})).toBe(
      'Math MCP: Add(a=3, b=7)'
    );
  });

  test('tool_use display name JSON-encodes object params instead of [object Object]', () => {
    expect(toolUseDisplayName('Edit', {edits: [{old: 'a', new: 'b'}]})).toBe(
      'Edit(edits=[{"old":"a","new":"b"}])'
    );
  });

  test('tool_use display name caps very long param values', () => {
    const long = 'x'.repeat(200);
    const name = toolUseDisplayName('Write', {content: long});
    expect(name.length).toBeLessThan(long.length);
    expect(name).toContain('...');
  });

  test('thinking display name is prefixed and abbreviated to 8 words', () => {
    expect(thinkingDisplayName('let me think about this')).toBe(
      'Thinking: let me think about this'
    );
    expect(
      thinkingDisplayName('one two three four five six seven eight nine')
    ).toBe('Thinking: one two three four five six seven eight...');
  });

  test('text display name is prefixed and abbreviated', () => {
    expect(textDisplayName('hello world')).toBe('Text: hello world');
  });

  test('turn display name uses first 8 words of the prompt, with ellipsis when longer', () => {
    expect(turnDisplayName('What is the weather')).toBe('What is the weather');
    expect(
      turnDisplayName('What is the weather in Tokyo today please tell me now')
    ).toBe('What is the weather in Tokyo today please...');
  });

  test('turn display name falls back to "Turn" when prompt is empty/null', () => {
    expect(turnDisplayName(null)).toBe('Turn');
    expect(turnDisplayName('')).toBe('Turn');
  });
});

describe('Claude Agent SDK — serializeMessage', () => {
  test('assistant message lifts the nested API message and tags the role', () => {
    const msg = {
      type: 'assistant',
      message: {model: 'claude-x', content: [{type: 'text', text: 'hi'}]},
      parent_tool_use_id: null,
    } as any;
    expect(serializeMessage(msg)).toEqual({
      role: 'assistant',
      model: 'claude-x',
      content: [{type: 'text', text: 'hi'}],
    });
  });

  test('user message lifts content blocks and tags the role', () => {
    const msg = {
      type: 'user',
      message: {
        content: [{type: 'tool_result', tool_use_id: 't1', content: 'ok'}],
      },
    } as any;
    expect(serializeMessage(msg)).toEqual({
      role: 'user',
      content: [{type: 'tool_result', tool_use_id: 't1', content: 'ok'}],
    });
  });

  test('system init message preserves its structured fields with role "system"', () => {
    // The SDK's system messages (e.g. subtype "init") carry their payload as
    // top-level fields, not under a nested `message`. serializeMessage must keep
    // them rather than dropping everything into an undefined `content`.
    const msg = {
      type: 'system',
      subtype: 'init',
      model: 'claude-x',
      tools: ['Bash', 'Read'],
      cwd: '/repo',
    } as any;
    expect(serializeMessage(msg)).toEqual({
      role: 'system',
      subtype: 'init',
      model: 'claude-x',
      tools: ['Bash', 'Read'],
      cwd: '/repo',
    });
  });
});

describe('Claude Agent SDK — toWeaveUsage', () => {
  test('maps the SDK camelCase ModelUsage shape to snake_case usage keys', () => {
    expect(
      toWeaveUsage({
        inputTokens: 10,
        outputTokens: 5,
        cacheReadInputTokens: 3,
        cacheCreationInputTokens: 2,
        // Non-token fields the rollup does not consume are dropped.
        costUSD: 0.01,
        contextWindow: 200000,
      })
    ).toEqual({
      input_tokens: 10,
      output_tokens: 5,
      cache_read_input_tokens: 3,
      cache_creation_input_tokens: 2,
    });
  });

  test('passes through fields already in snake_case (aggregate usage)', () => {
    expect(toWeaveUsage({input_tokens: 7, output_tokens: 9})).toEqual({
      input_tokens: 7,
      output_tokens: 9,
    });
  });

  test('omits absent token fields rather than emitting nulls', () => {
    expect(toWeaveUsage({inputTokens: 4})).toEqual({input_tokens: 4});
  });
});

describe('Claude Agent SDK — tracer', () => {
  let server: InMemoryTraceServer;
  const project = 'test-project-cas';

  beforeEach(() => {
    server = new InMemoryTraceServer();
    initWithCustomTraceServer(project, server);
  });

  test('emits a root agent call with thinking, text, and tool-use children', async () => {
    const tracer = new ClaudeAgentTracer({
      client: requireGlobalClient(),
      prompt: 'What is the weather in Tokyo?',
    });

    tracer.processMessage({
      type: 'assistant',
      message: {
        model: 'claude-x',
        content: [
          {type: 'thinking', thinking: 'I should check the weather'},
          {type: 'text', text: 'Let me check.'},
          {
            type: 'tool_use',
            id: 'tu1',
            name: 'get_weather',
            input: {city: 'Tokyo'},
          },
        ],
      },
    } as any);
    tracer.processMessage({
      type: 'user',
      message: {
        content: [
          {type: 'tool_result', tool_use_id: 'tu1', content: 'Sunny, 22C'},
        ],
      },
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'success',
      is_error: false,
      result: 'It is sunny.',
      total_cost_usd: 0.01,
      duration_ms: 1234,
      num_turns: 1,
      // Real SDK shape: ModelUsage values are camelCase. The tracer must map
      // them to Weave's snake_case usage keys or token/cost rollup breaks.
      modelUsage: {
        'claude-x': {
          inputTokens: 10,
          outputTokens: 5,
          cacheReadInputTokens: 3,
        },
      },
    } as any);

    const calls = await server.getCalls(project);
    expect(calls).toHaveLength(4);

    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query')!;
    expect(root.attributes.kind).toBe('agent');
    expect(root.attributes.integration).toMatchObject({
      name: 'claude_agent_sdk',
    });
    expect(root.display_name).toBe('What is the weather in Tokyo?');
    expect(root.inputs).toEqual({prompt: 'What is the weather in Tokyo?'});
    expect(root.ended_at).toBeTruthy();
    expect(root.output.status).toBe('completed');
    expect(root.output.result).toBe('It is sunny.');
    expect(root.output.total_cost_usd).toBe(0.01);
    expect(root.summary.usage['claude-x']).toMatchObject({
      requests: 1,
      input_tokens: 10,
      output_tokens: 5,
      cache_read_input_tokens: 3,
    });
    // camelCase keys must not leak through into the usage summary.
    expect(root.summary.usage['claude-x'].inputTokens).toBeUndefined();

    const thinking = calls.find(
      c => c.op_name === 'claude_agent_sdk.thinking'
    )!;
    expect(thinking.attributes.kind).toBe('llm');
    expect(thinking.parent_id).toBe(root.id);
    expect(thinking.output).toEqual({thinking: 'I should check the weather'});

    const text = calls.find(c => c.op_name === 'claude_agent_sdk.text')!;
    expect(text.attributes.kind).toBe('llm');
    expect(text.parent_id).toBe(root.id);
    expect(text.output).toMatchObject({
      text: 'Let me check.',
      model: 'claude-x',
    });

    const tool = calls.find(
      c => c.op_name === 'claude_agent_sdk.tool_use.get_weather'
    )!;
    expect(tool.attributes.kind).toBe('tool');
    expect(tool.parent_id).toBe(root.id);
    expect(tool.display_name).toBe('get_weather(city="Tokyo")');
    expect(tool.output).toMatchObject({
      tool_use_id: 'tu1',
      content: 'Sunny, 22C',
    });
    expect(tool.ended_at).toBeTruthy();

    for (const c of calls) {
      expect(c.trace_id).toBe(root.trace_id);
    }
  });

  test('finalize on an error result marks the root call with an exception', async () => {
    const tracer = new ClaudeAgentTracer({
      client: requireGlobalClient(),
      prompt: 'do something',
    });
    tracer.processMessage({
      type: 'assistant',
      message: {model: 'm', content: [{type: 'text', text: 'trying'}]},
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'error_during_execution',
      is_error: true,
      errors: ['boom'],
      total_cost_usd: 0,
      num_turns: 1,
    } as any);

    const calls = await server.getCalls(project);
    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query')!;
    expect(root.output.status).toBe('error');
    expect(root.exception).toContain('boom');
  });

  test('finalize closes tool calls still open (no matching tool_result)', async () => {
    const tracer = new ClaudeAgentTracer({
      client: requireGlobalClient(),
      prompt: 'p',
    });
    tracer.processMessage({
      type: 'assistant',
      message: {
        model: 'm',
        content: [
          {type: 'tool_use', id: 'tu9', name: 'Bash', input: {command: 'ls'}},
        ],
      },
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'success',
      is_error: false,
    } as any);

    const calls = await server.getCalls(project);
    const tool = calls.find(
      c => c.op_name === 'claude_agent_sdk.tool_use.Bash'
    )!;
    expect(tool.ended_at).toBeTruthy();
    // A clean finish closes a leftover tool call without an exception.
    expect(tool.exception).toBeUndefined();
  });

  test('summary falls back to aggregate usage keyed by root model when modelUsage is absent', async () => {
    const tracer = new ClaudeAgentTracer({
      client: requireGlobalClient(),
      prompt: 'hi',
    });
    tracer.processMessage({
      type: 'assistant',
      message: {model: 'claude-y', content: [{type: 'text', text: 'hi'}]},
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'success',
      is_error: false,
      // Aggregate usage only (snake_case, no per-model modelUsage).
      usage: {input_tokens: 11, output_tokens: 4},
    } as any);

    const calls = await server.getCalls(project);
    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query')!;
    expect(root.summary.usage['claude-y']).toMatchObject({
      requests: 1,
      input_tokens: 11,
      output_tokens: 4,
    });
  });

  test('a tool_result flagged is_error finishes the tool call with an exception', async () => {
    const tracer = new ClaudeAgentTracer({
      client: requireGlobalClient(),
      prompt: 'p',
    });
    tracer.processMessage({
      type: 'assistant',
      message: {
        model: 'm',
        content: [
          {type: 'tool_use', id: 'tu5', name: 'Bash', input: {command: 'boom'}},
        ],
      },
    } as any);
    tracer.processMessage({
      type: 'user',
      message: {
        content: [
          {
            type: 'tool_result',
            tool_use_id: 'tu5',
            content: 'command not found',
            is_error: true,
          },
        ],
      },
    } as any);
    tracer.finalize({
      type: 'result',
      subtype: 'success',
      is_error: false,
    } as any);

    const calls = await server.getCalls(project);
    const tool = calls.find(
      c => c.op_name === 'claude_agent_sdk.tool_use.Bash'
    )!;
    expect(tool.exception).toContain('command not found');
  });

  test('finalize with a stream error marks still-open tool calls as interrupted', async () => {
    const tracer = new ClaudeAgentTracer({
      client: requireGlobalClient(),
      prompt: 'p',
    });
    tracer.processMessage({
      type: 'assistant',
      message: {
        model: 'm',
        content: [
          {type: 'tool_use', id: 'tuX', name: 'Bash', input: {command: 'ls'}},
        ],
      },
    } as any);
    tracer.finalize(undefined, new Error('subprocess crashed'));

    const calls = await server.getCalls(project);
    const tool = calls.find(
      c => c.op_name === 'claude_agent_sdk.tool_use.Bash'
    )!;
    expect(tool.exception).toContain('subprocess crashed');
    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query')!;
    expect(root.output.status).toBe('error');
  });
});

describe('Claude Agent SDK — query() patch', () => {
  let server: InMemoryTraceServer;
  const project = 'test-project-cas-patch';

  beforeEach(() => {
    server = new InMemoryTraceServer();
    initWithCustomTraceServer(project, server);
  });

  // Stand-in for `@anthropic-ai/claude-agent-sdk`: query() returns a Query
  // (an async generator extended with control methods like interrupt()).
  function fakeSdk(
    messages: any[],
    extras: Record<string, any> = {}
  ): {query: (args: any) => any} {
    return {
      query: (_args: any) => {
        async function* gen() {
          for (const m of messages) {
            yield m;
          }
        }
        const q = gen() as any;
        Object.assign(q, extras);
        return q;
      },
    };
  }

  test('wrapping query() traces streamed messages and yields them unchanged', async () => {
    const sdk = fakeSdk([
      {
        type: 'assistant',
        message: {model: 'claude-x', content: [{type: 'text', text: 'hello'}]},
      },
      {
        type: 'result',
        subtype: 'success',
        is_error: false,
        result: 'done',
        modelUsage: {'claude-x': {inputTokens: 1, outputTokens: 2}},
      },
    ]);
    patchClaudeAgentSdk(sdk);

    const seen: string[] = [];
    for await (const m of sdk.query({prompt: 'hi there'})) {
      seen.push(m.type);
    }
    expect(seen).toEqual(['assistant', 'result']);

    const calls = await server.getCalls(project);
    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query')!;
    expect(root).toBeDefined();
    expect(root.inputs).toEqual({prompt: 'hi there'});
    expect(root.output.status).toBe('completed');
    expect(root.output.result).toBe('done');
    expect(
      calls.find(c => c.op_name === 'claude_agent_sdk.text')
    ).toBeDefined();
  });

  test('forwards Query interface methods (e.g. interrupt) to the underlying query', async () => {
    const interrupt = jest.fn(async () => {});
    const sdk = fakeSdk(
      [{type: 'result', subtype: 'success', is_error: false}],
      {
        interrupt,
      }
    );
    patchClaudeAgentSdk(sdk);

    const q = sdk.query({prompt: 'x'});
    await q.interrupt();
    expect(interrupt).toHaveBeenCalledTimes(1);

    // Membership checks must agree with what `get` actually serves: forwarded
    // control methods and generator-protocol members both report present.
    expect('interrupt' in q).toBe(true);
    expect(Symbol.asyncIterator in q).toBe(true);
    expect('nonexistent' in q).toBe(false);

    // drain so the root call finalizes
    for await (const _msg of q) {
      void _msg;
    }
  });

  test('records an exception on the root call when the stream throws mid-iteration', async () => {
    const boom = new Error('subprocess crashed');
    const sdk = {
      query: (_args: any) => {
        async function* gen() {
          yield {
            type: 'assistant',
            message: {
              model: 'claude-x',
              content: [{type: 'text', text: 'starting'}],
            },
          };
          throw boom;
        }
        return gen() as any;
      },
    };
    patchClaudeAgentSdk(sdk);

    // The error must still propagate to the caller...
    const drain = (async () => {
      for await (const _msg of sdk.query({prompt: 'go'})) {
        void _msg;
      }
    })();
    await expect(drain).rejects.toThrow('subprocess crashed');

    // ...and the root call must be finalized as an error, not a completion.
    const calls = await server.getCalls(project);
    const root = calls.find(c => c.op_name === 'claude_agent_sdk.query')!;
    expect(root.output.status).toBe('error');
    expect(root.exception).toContain('subprocess crashed');
  });

  test('passes through untouched when no weave client is initialized', async () => {
    setGlobalClient(null);
    const sdk = fakeSdk([
      {type: 'assistant', message: {content: [{type: 'text', text: 'hi'}]}},
      {type: 'result', subtype: 'success'},
    ]);
    patchClaudeAgentSdk(sdk);

    const seen: string[] = [];
    for await (const m of sdk.query({prompt: 'x'})) {
      seen.push(m.type);
    }
    expect(seen).toEqual(['assistant', 'result']);
  });

  test('patching twice does not double-wrap query()', async () => {
    const sdk = fakeSdk([
      {
        type: 'assistant',
        message: {model: 'claude-x', content: [{type: 'text', text: 'hi'}]},
      },
      {type: 'result', subtype: 'success', is_error: false},
    ]);
    patchClaudeAgentSdk(sdk);
    const afterFirstPatch = sdk.query;
    patchClaudeAgentSdk(sdk);
    // The PATCHED marker makes the second patch a no-op — same wrapped fn.
    expect(sdk.query).toBe(afterFirstPatch);

    // And a single query() yields exactly one root call (not two layers).
    for await (const _msg of sdk.query({prompt: 'hi'})) {
      void _msg;
    }
    const calls = await server.getCalls(project);
    expect(
      calls.filter(c => c.op_name === 'claude_agent_sdk.query')
    ).toHaveLength(1);
  });
});
