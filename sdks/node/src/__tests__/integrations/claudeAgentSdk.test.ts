import {SpanStatusCode} from '@opentelemetry/api';

import {ATTR_GEN_AI_INPUT_MESSAGES} from '../../genai/semconv';
import {
  patchClaudeAgentSdk,
  wrapClaudeAgentSdk,
} from '../../integrations/claudeAgentSdk';
import {toWeaveUsage} from '../../integrations/claude-agent-sdk/messages';
import {
  clearGlobalClient,
  findSpan,
  setupExporterPerTest,
  setupGenAITestEnvironment,
} from '../genai/common';
import type {NonNullableUsage} from '@anthropic-ai/claude-agent-sdk';

const INVOKE = 'invoke_agent claude_agent_sdk';

describe('Claude Agent SDK — toWeaveUsage', () => {
  test('maps the camelCase ModelUsage shape, dropping non-token fields', () => {
    // A complete ModelUsage: the four token fields map to snake_case, and the
    // non-token fields (web search, cost, context window, max output) are
    // dropped — the usage/cost rollup keys only on the token counts.
    expect(
      toWeaveUsage({
        inputTokens: 10,
        outputTokens: 5,
        cacheReadInputTokens: 3,
        cacheCreationInputTokens: 2,
        webSearchRequests: 1,
        costUSD: 0.01,
        contextWindow: 200000,
        maxOutputTokens: 8192,
      })
    ).toEqual({
      input_tokens: 10,
      output_tokens: 5,
      cache_read_input_tokens: 3,
      cache_creation_input_tokens: 2,
    });
  });

  test('passes through the snake_case aggregate (NonNullableUsage) token keys', () => {
    // NonNullableUsage carries ~11 fields, several nested (cache_creation,
    // iterations, …); cast a token-only literal since the rest are irrelevant
    // to the mapping. The `in` check takes the snake_case branch (no camelCase
    // key present), so the four token counts pass through unchanged.
    const aggregate = {
      input_tokens: 7,
      output_tokens: 9,
      cache_read_input_tokens: 4,
      cache_creation_input_tokens: 2,
    } as NonNullableUsage;
    expect(toWeaveUsage(aggregate)).toEqual({
      input_tokens: 7,
      output_tokens: 9,
      cache_read_input_tokens: 4,
      cache_creation_input_tokens: 2,
    });
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
          for (const message of messages) {
            yield message;
          }
        }
        const query = gen() as any;
        Object.assign(query, extras);
        return query;
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
        modelUsage: {
          'claude-x': {
            inputTokens: 1,
            outputTokens: 2,
            cacheReadInputTokens: 0,
            cacheCreationInputTokens: 0,
          },
        },
      },
    ]);
    patchClaudeAgentSdk(sdk);

    const seen: string[] = [];
    for await (const message of sdk.query({prompt: 'hi there'})) {
      seen.push(message.type);
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

    const query = sdk.query({prompt: 'x'});
    await query.interrupt();
    expect(interrupt).toHaveBeenCalledTimes(1);

    // Membership checks must agree with what `get` actually serves: forwarded
    // control methods and generator-protocol members both report present.
    expect('interrupt' in query).toBe(true);
    expect(Symbol.asyncIterator in query).toBe(true);
    expect('nonexistent' in query).toBe(false);

    // drain so the root span finalizes
    for await (const _msg of query) {
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
    for await (const message of sdk.query({prompt: 'x'})) {
      seen.push(message.type);
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
        for (const message of messages) {
          yield message;
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
    for await (const message of patched.query({prompt: 'hi there'})) {
      seen.push(message.type);
    }
    expect(seen).toEqual(['assistant', 'result']);

    expect(findSpan(getExporter().getFinishedSpans(), INVOKE)).toBeDefined();
  });

  test('wrapClaudeAgentSdk() returns a traced module view for manual instrumentation', async () => {
    // The public manual-instrumentation entry point. Mirrors a user reaching
    // for it when the auto-instrumentation hooks don't fire: they import the
    // module and wrap it themselves. The SDK's `query` is a getter-only export,
    // so callers must use the returned view rather than the original binding.
    const messages = [
      {
        type: 'assistant',
        message: {model: 'claude-x', content: [{type: 'text', text: 'hi'}]},
      },
      {type: 'result', subtype: 'success', is_error: false, result: 'done'},
    ];
    const realQuery = (_args: any) => {
      async function* gen() {
        for (const message of messages) {
          yield message;
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

    const {query} = wrapClaudeAgentSdk(mod);

    const seen: string[] = [];
    for await (const message of query({prompt: 'hi there'})) {
      seen.push(message.type);
    }
    expect(seen).toEqual(['assistant', 'result']);
    expect(findSpan(getExporter().getFinishedSpans(), INVOKE)).toBeDefined();
  });
});
