/**
 * End-to-end demo of the Weave Session SDK (TypeScript).
 *
 * Builds a small multi-turn agent conversation by hand and emits OTel
 * spans to a real Weave trace server. Runs entirely offline (no OpenAI
 * API call needed) — the "LLM call" is just a string we record onto an
 * `LLM` span. The goal is to verify the wire format end-to-end, not to
 * exercise an LLM provider.
 *
 * Usage:
 *
 *     # API key is resolved automatically from $WANDB_API_KEY or ~/.netrc
 *     # (the same lookup `weave.init()` uses internally).
 *
 *     # Optional (defaults shown):
 *     #   WANDB_PROJECT=andrew/otel-testing
 *     #   WANDB_BASE_URL=https://api.wandb.ai
 *
 *     pnpm tsx examples/session.ts
 *
 * Requires Node (not Bun) since `tsx` doesn't run cleanly under Bun's
 * node-compat shim. If `node --version` shows you have Bun's wrapper,
 * point pnpm at a real Node install:
 *
 *     PATH="$HOME/.nvm/versions/node/v20.19.4/bin:$PATH" pnpm tsx examples/session.ts
 *
 * What it does:
 *
 *  1. `weave.init(project)` — authenticates and obtains the trace server URL.
 *  2. Wires a `BasicTracerProvider` whose OTLP exporter points at
 *     `${baseUrl}/otel/v1/traces` (the same endpoint `piCodingAgent.ts`
 *     uses). Registers it as the global tracer provider so the Session
 *     SDK's `trace.getTracer('weave.session')` lands on it.
 *  3. Walks through one session with two turns:
 *      - Turn 1: a chat call (LLM span) and a tool call (Tool span).
 *      - Turn 2: a chat call with reasoning attached.
 *  4. Flushes spans and exits.
 *
 * After it finishes, open the Weave UI for the project and look for a
 * trace named `invoke_agent <agentName>` — there will be one trace per
 * turn, since `continueParentTrace` defaults to false.
 */

import {Resource} from '@opentelemetry/resources';
import {
  BasicTracerProvider,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
import {OTLPTraceExporter} from '@opentelemetry/exporter-trace-otlp-proto';
import {trace} from '@opentelemetry/api';
// Import directly from `../src` so the example runs under `tsx` without a
// prior build step. Other examples import from `'weave'`, which requires
// either a `pnpm link --global weave` or a built `dist/`. Relative imports
// keep this script "clone, run."
import * as weave from '../src';
import {getWandbConfigs} from '../src/wandb/settings';

async function main(): Promise<void> {
  const project = process.env.WANDB_PROJECT ?? 'andrew/otel-testing';

  // 1. Initialize the Weave client. `getWandbConfigs()` resolves the API
  //    key from $WANDB_API_KEY or ~/.netrc (same lookup `init` uses).
  const client = await weave.init(project);
  const {apiKey} = getWandbConfigs();
  const traceServerUrl = client.traceServerApi.baseUrl;
  const [entity, projectName] = client.projectId.split('/');

  // 2. Configure OTel to export to the Weave OTLP endpoint. The Session SDK
  //    calls `trace.getTracer('weave.session')` on the global provider, so
  //    we install our provider as global.
  const authHeader = `Basic ${Buffer.from(`api:${apiKey}`).toString('base64')}`;
  const provider = new BasicTracerProvider({
    resource: new Resource({
      'wandb.entity': entity,
      'wandb.project': projectName,
    }),
    spanProcessors: [
      new SimpleSpanProcessor(
        new OTLPTraceExporter({
          url: `${traceServerUrl}/otel/v1/traces`,
          headers: {
            Authorization: authHeader,
            project_id: client.projectId,
          },
        })
      ),
    ],
  });
  trace.setGlobalTracerProvider(provider);

  // 3. Walk through a small conversation.
  const session = weave.startSession({
    agentName: 'weather-agent',
    model: 'gpt-4o',
    sessionName: 'demo session',
  });
  console.log(`Started session ${session.sessionId}`);

  // --- Turn 1: chat + tool call ---
  {
    const turn = session.startTurn({
      userMessage: "what's the weather in Tokyo?",
    });

    const llm = turn.llm({providerName: 'openai'}).start();
    llm.record({
      inputMessages: [weave.Message.user("what's the weather in Tokyo?")],
      outputMessages: [
        weave.Message.assistant('Let me look that up.', {
          toolCalls: [
            weave.toolCallPart({
              id: 'call_1',
              name: 'get_weather',
              arguments: {city: 'Tokyo', units: 'fahrenheit'},
            }),
          ],
        }),
      ],
      usage: new weave.Usage({inputTokens: 25, outputTokens: 12}),
      finishReasons: ['tool_calls'],
      responseId: 'resp_demo_1',
      responseModel: 'gpt-4o-2024-08-06',
    });
    llm.end();

    const tool = weave.startTool({
      name: 'get_weather',
      toolCallId: 'call_1',
      arguments: {city: 'Tokyo', units: 'fahrenheit'},
    });
    tool.result = {tempF: 75, conditions: 'clear', humidity: 45};
    tool.end();

    const llm2 = turn.llm({providerName: 'openai'}).start();
    llm2.record({
      inputMessages: [
        weave.Message.user("what's the weather in Tokyo?"),
        weave.Message.toolResult('call_1', {tempF: 75, conditions: 'clear'}),
      ],
      outputMessages: [
        weave.Message.assistant("It's 75°F and clear in Tokyo right now."),
      ],
      usage: new weave.Usage({inputTokens: 58, outputTokens: 14}),
      finishReasons: ['stop'],
    });
    llm2.end();

    turn.end();
    console.log('  Turn 1 emitted');
  }

  // --- Turn 2: chat with reasoning ---
  {
    const turn = session.startTurn({userMessage: 'and Osaka?'});

    const llm = turn.llm({providerName: 'openai'}).start();
    llm.record({
      inputMessages: [weave.Message.user('and Osaka?')],
      outputMessages: [
        weave.Message.assistant('Osaka is 72°F and partly cloudy.'),
      ],
      reasoning: 'User is asking about a different city. Same tool, new args.',
      usage: new weave.Usage({inputTokens: 30, outputTokens: 11}),
      finishReasons: ['stop'],
    });
    llm.end();

    turn.end();
    console.log('  Turn 2 emitted');
  }

  session.end();

  // 4. Flush spans before exit. SimpleSpanProcessor exports synchronously
  //    on `span.end()`, but `shutdown()` waits for any in-flight network
  //    request to settle and is the safe choice in scripts.
  await provider.shutdown();
  console.log('Done. Open Weave UI for', client.projectId);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
