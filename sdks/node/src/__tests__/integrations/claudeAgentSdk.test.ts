import {SpanStatusCode} from '@opentelemetry/api';

import {ATTR_GEN_AI_INPUT_MESSAGES} from '../../genai/semconv';
import {patchClaudeAgentSdk} from '../../integrations/claudeAgentSdk';
import {toWeaveUsage} from '../../integrations/claude-agent-sdk/messages';
import {
  clearGlobalClient,
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from '../genai/common';

const INVOKE = 'invoke_agent claude_agent_sdk';

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

describe('Claude Agent SDK — query() patch', () => {
  setupGenAITestEnvironment();
  const getExporter = setupExporterPerTest();

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

  test('wrapping query() emits agent spans and yields messages unchanged', async () => {
    const sdk = fakeSdk([
      {
        type: 'assistant',
        session_id: 'sess-1',
        message: {model: 'claude-x', content: [{type: 'text', text: 'hello'}]},
      },
      {
        type: 'result',
        subtype: 'success',
        session_id: 'sess-1',
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

    const spans = getExporter().getFinishedSpans();
    const invoke = findSpan(spans, INVOKE);
    expect(
      JSON.parse(invoke.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string)
    ).toEqual([{role: 'user', content: 'hi there'}]);
    expect(spans.some(s => s.name === 'chat claude-x')).toBe(true);
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

    // drain so the root span finalizes
    for await (const _msg of q) {
      void _msg;
    }
  });

  test('records an exception on the root span when the stream throws mid-iteration', async () => {
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

    // ...and the root span must be finalized as an error, not a completion.
    const invoke = findSpan(getExporter().getFinishedSpans(), INVOKE);
    expect(invoke.status.code).toBe(SpanStatusCode.ERROR);
    expect(invoke.status.message).toContain('subprocess crashed');
  });

  test('passes through untouched when no weave client is initialized', async () => {
    clearGlobalClient();
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
    // No client → no tracer constructed → no spans emitted.
    expect(getExporter().getFinishedSpans()).toHaveLength(0);
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

    // And a single query() yields exactly one root span (not two layers).
    for await (const _msg of sdk.query({prompt: 'hi'})) {
      void _msg;
    }
    const roots = getExporter()
      .getFinishedSpans()
      .filter(s => s.name === INVOKE);
    expect(roots).toHaveLength(1);
  });

  test('wraps a getter-only query export (ESM→CJS interop) via the return value', async () => {
    // The SDK ships as ESM (`sdk.mjs`). Loaded through a CJS interop layer
    // (tsx/esbuild), its named exports become non-writable, non-configurable
    // getters, so `exports.query = ...` throws. The hook must instead return a
    // usable module view, mirroring how the require() loader uses the return.
    const messages = [
      {
        type: 'assistant',
        message: {model: 'claude-x', content: [{type: 'text', text: 'hi'}]},
      },
      {type: 'result', subtype: 'success', is_error: false, result: 'done'},
    ];
    const realQuery = (_args: any) => {
      async function* gen() {
        for (const m of messages) {
          yield m;
        }
      }
      return gen() as any;
    };
    const mod: any = {};
    Object.defineProperty(mod, '__esModule', {value: true});
    Object.defineProperty(mod, 'query', {
      get: () => realQuery,
      enumerable: true,
    });

    const patched = patchClaudeAgentSdk(mod);
    // Other exports (e.g. the ESM interop marker) remain visible.
    expect(patched.__esModule).toBe(true);

    const seen: string[] = [];
    for await (const m of patched.query({prompt: 'hi there'})) {
      seen.push(m.type);
    }
    expect(seen).toEqual(['assistant', 'result']);

    expect(findSpan(getExporter().getFinishedSpans(), INVOKE)).toBeDefined();
  });
});
