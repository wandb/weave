import {SpanStatusCode} from '@opentelemetry/api';

import {getCurrentLLM, getCurrentTurn} from '../../genai';
import {
  ATTR_GEN_AI_CONVERSATION_ID,
  ATTR_GEN_AI_INPUT_MESSAGES,
  ATTR_GEN_AI_OUTPUT_MESSAGES,
  ATTR_GEN_AI_USAGE_INPUT_TOKENS,
} from '../../genai/semconv';
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

const INVOKE = 'invoke_agent';

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
    expect(spans.some(s => s.name === 'chat')).toBe(true);
  });

  test('streaming input emits one root per user turn', async () => {
    let receivedOptions: Record<string, unknown> | undefined;
    async function* prompts() {
      yield {
        type: 'user',
        message: {role: 'user', content: 'first question'},
        parent_tool_use_id: null,
      };
      yield {
        type: 'user',
        message: {role: 'user', content: 'second question'},
        parent_tool_use_id: null,
      };
    }

    const sdk = {
      query: ({
        prompt,
        options,
      }: {
        prompt: AsyncIterable<any>;
        options?: Record<string, unknown>;
      }) => {
        receivedOptions = options;
        async function* gen() {
          let turn = 0;
          for await (const _input of prompt) {
            turn += 1;
            yield {
              type: 'assistant',
              session_id: 'sess-multi',
              message: {
                model: `claude-${turn}`,
                content: [{type: 'text', text: `response-${turn}`}],
              },
            };
            yield {
              type: 'result',
              subtype: 'success',
              session_id: 'sess-multi',
              is_error: false,
              result: `result-${turn}`,
              total_cost_usd: turn / 100,
              modelUsage: {
                [`claude-${turn}`]: {
                  inputTokens: turn,
                  outputTokens: turn + 1,
                  cacheReadInputTokens: 0,
                  cacheCreationInputTokens: 0,
                },
              },
            };
          }
        }
        return gen() as any;
      },
    };
    patchClaudeAgentSdk(sdk);

    const query = sdk.query({
      prompt: prompts(),
      options: {forwardSubagentText: true},
    });
    await expect(query.next()).resolves.toMatchObject({
      value: {type: 'assistant'},
      done: false,
    });
    await expect(query.next()).resolves.toMatchObject({
      value: {type: 'result', result: 'result-1'},
      done: false,
    });
    expect(
      getExporter()
        .getFinishedSpans()
        .filter(span => span.name === INVOKE)
    ).toHaveLength(1);

    for await (const _message of query) {
      void _message;
    }

    const roots = getExporter()
      .getFinishedSpans()
      .filter(span => span.name === INVOKE);
    expect(roots).toHaveLength(2);
    expect(receivedOptions).toEqual({forwardSubagentText: true});
    expect(
      roots.map(root => ({
        conversationId: root.attributes[ATTR_GEN_AI_CONVERSATION_ID],
        input: JSON.parse(
          root.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string
        ),
        output: JSON.parse(
          root.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string
        ),
      }))
    ).toEqual([
      {
        conversationId: 'sess-multi',
        input: [{role: 'user', content: 'first question'}],
        output: [{role: 'assistant', content: 'result-1'}],
      },
      {
        conversationId: 'sess-multi',
        input: [{role: 'user', content: 'second question'}],
        output: [{role: 'assistant', content: 'result-2'}],
      },
    ]);
  });

  test('traces user messages sent through Query.streamInput()', async () => {
    const streamInput = jest.fn(async (stream: AsyncIterable<any>) => {
      for await (const _message of stream) {
        void _message;
      }
    });
    const sdk = fakeSdk(
      [
        {
          type: 'assistant',
          session_id: 'sess-stream-input',
          message: {
            model: 'claude-x',
            content: [{type: 'text', text: 'response'}],
          },
        },
        {
          type: 'result',
          subtype: 'success',
          session_id: 'sess-stream-input',
          is_error: false,
          result: 'done',
          modelUsage: {},
        },
      ],
      {streamInput}
    );
    patchClaudeAgentSdk(sdk);

    const emptyPrompt: AsyncIterable<any> = {
      [Symbol.asyncIterator]: () => ({
        next: async () => ({done: true, value: undefined}),
      }),
    };
    async function* nextTurn() {
      yield {
        type: 'user',
        message: {role: 'user', content: 'sent later'},
        parent_tool_use_id: null,
      };
    }

    const query = sdk.query({prompt: emptyPrompt});
    await query.streamInput(nextTurn());
    for await (const _message of query) {
      void _message;
    }

    expect(streamInput).toHaveBeenCalledTimes(1);
    const root = findSpan(getExporter().getFinishedSpans(), INVOKE);
    expect(
      JSON.parse(root.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string)
    ).toEqual([{role: 'user', content: 'sent later'}]);
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
    expect(invoke.status.message).toBe('subprocess crashed');
  });

  test('isolates two interleaved query streams and preserves each trace tree', async () => {
    let arrivals = 0;
    let releaseBoth!: () => void;
    const bothQueriesStarted = new Promise<void>(resolve => {
      releaseBoth = resolve;
    });

    const sdk = {
      query: ({prompt}: {prompt: string}) => {
        const suffix = prompt === 'first' ? 'a' : 'b';
        const sessionId = `session-${suffix}`;
        const model = `claude-${suffix}`;
        async function* gen() {
          yield {
            type: 'assistant',
            session_id: sessionId,
            message: {
              model,
              content: [{type: 'text', text: `response-${suffix}`}],
            },
          };
          arrivals += 1;
          if (arrivals === 2) {
            releaseBoth();
          }
          await bothQueriesStarted;
          yield {
            type: 'result',
            subtype: 'success',
            session_id: sessionId,
            is_error: false,
            result: `done-${suffix}`,
            total_cost_usd: 0.01,
            num_turns: 1,
            modelUsage: {
              [model]: {
                inputTokens: 1,
                outputTokens: 2,
                cacheReadInputTokens: 0,
                cacheCreationInputTokens: 0,
              },
            },
          };
        }
        return gen() as any;
      },
    };
    patchClaudeAgentSdk(sdk);

    const drain = async (prompt: string) => {
      const seen: string[] = [];
      for await (const message of sdk.query({prompt})) {
        seen.push(message.type);
      }
      return seen;
    };
    await expect(
      Promise.all([drain('first'), drain('second')])
    ).resolves.toEqual([
      ['assistant', 'result'],
      ['assistant', 'result'],
    ]);
    expect(getCurrentTurn()).toBeUndefined();
    expect(getCurrentLLM()).toBeUndefined();

    const spans = getExporter().getFinishedSpans();
    const roots = spans.filter(span => span.name === INVOKE);
    expect(roots).toHaveLength(2);

    for (const [suffix, prompt] of [
      ['a', 'first'],
      ['b', 'second'],
    ] as const) {
      const sessionId = `session-${suffix}`;
      const root = roots.find(
        span => span.attributes[ATTR_GEN_AI_CONVERSATION_ID] === sessionId
      )!;
      expect(
        JSON.parse(root.attributes[ATTR_GEN_AI_INPUT_MESSAGES] as string)
      ).toEqual([{role: 'user', content: prompt}]);
      expect(
        JSON.parse(root.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] as string)
      ).toEqual([{role: 'assistant', content: `done-${suffix}`}]);

      const children = spans.filter(
        span => span.parentSpanId === root.spanContext().spanId
      );
      expect(children).toHaveLength(2);
      expect(
        children.map(span => ({
          conversationId: span.attributes[ATTR_GEN_AI_CONVERSATION_ID],
          hasOutput: span.attributes[ATTR_GEN_AI_OUTPUT_MESSAGES] !== undefined,
          hasUsage:
            span.attributes[ATTR_GEN_AI_USAGE_INPUT_TOKENS] !== undefined,
          name: span.name,
          traceId: span.spanContext().traceId,
        }))
      ).toEqual([
        {
          conversationId: sessionId,
          hasOutput: true,
          hasUsage: false,
          name: 'chat',
          traceId: root.spanContext().traceId,
        },
        {
          conversationId: sessionId,
          hasOutput: false,
          hasUsage: true,
          name: 'chat',
          traceId: root.spanContext().traceId,
        },
      ]);
    }
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
