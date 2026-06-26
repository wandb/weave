/**
 * OpenAI Agents → Weave: a multi-agent example that self-checks offline.
 *
 * Code orchestration (https://openai.github.io/openai-agents-python/multi_agent/):
 * @openai/agents has no Sequential/Parallel/Loop workflow agents the way
 * Google ADK does, so the equivalent control flow is plain TS. Five plain
 * `Agent` instances are wired together by the `research()` function:
 *
 *   research(prompt) = withTrace('research_pipeline', async () => {
 *     ├─ await run(planner, prompt)                          // Sequential
 *     ├─ await Promise.all([
 *     │     run(weather, prompt),                            // Parallel
 *     │     run(market, prompt),                             // (recon_team)
 *     │  ])
 *     ├─ for i in 1..2: await run(critic, …)                 // Loop
 *     └─ await run(synthesist, …)                            // Sequential
 *   })
 *
 * `withTrace` ties the six `run()`s into one OTel trace named
 * `research_pipeline` — that's the only thing standing in for ADK's
 * Sequential agent.
 *
 * Modes:
 *   (default)     offline self-check — a scripted model, no creds, no network.
 *                 Spans are captured in-memory and asserted. Exits 0 on
 *                 success, 1 on failure.
 *   WEAVE_LIVE=1  real weave.init() + real OpenAI → spans land in the Agents
 *                 view of your Weave project.
 *
 * Run from sdks/node. Build first so `weave` resolves to dist:
 *
 *   npm run build
 *   node --import=weave/instrument --import=tsx examples/openaiAgentsAdvanced.ts        # offline
 *   WEAVE_LIVE=1 WANDB_API_KEY=… WANDB_PROJECT=<entity>/<project> OPENAI_API_KEY=… \
 *     node --import=weave/instrument --import=tsx examples/openaiAgentsAdvanced.ts      # live
 */

import * as weave from 'weave';
import {
  Agent,
  OpenAIResponsesModel,
  run,
  tool,
  withTrace,
} from '@openai/agents';
import type {Model, ModelRequest} from '@openai/agents';
import OpenAI from 'openai';
import {z} from 'zod';
// Offline span capture only. A custom SpanProcessor is the public seam
// (weave.init({genai: {spanProcessor}})); the OTel test exporter lets the
// offline check read spans back. A live app never imports these.
import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
const WANDB_PROJECT = process.env.WANDB_PROJECT || 'examples-openai-agents-2';
const LIVE_MODEL = 'gpt-4o-mini';
const LIVE = !!process.env.WEAVE_LIVE;
const PROMPT =
  'Plan a day in Paris: check the weather and the AAPL stock price, then critique the plan.';

// A model resolver is the seam that lets both modes share one graph: live
// returns a model name; the offline check returns a scripted MockAgent per
// agent name.
type ModelFor = (agentName: string) => string | Model;

// ╔══════════════════════════════════════════════════════════════════════╗
// ║  USER CODE — this is the whole integration. Everything below the        ║
// ║  "END USER CODE" banner is offline-test scaffolding, not part of        ║
// ║  using Weave.                                                           ║
// ╚══════════════════════════════════════════════════════════════════════╝

const getWeather = tool({
  name: 'get_weather',
  description: 'Current weather for a city.',
  parameters: z.object({city: z.string().describe('the city to look up')}),
  async execute({city}) {
    return `${city}: Sunny, 21°C`;
  },
});

const getStockPrice = tool({
  name: 'get_stock_price',
  description: 'Latest stock price for a ticker.',
  parameters: z.object({ticker: z.string().describe('the ticker symbol')}),
  async execute({ticker}) {
    return `${ticker}: $199.98`;
  },
});

// Code-orchestration shape: workflow agents like ADK's Sequential / Parallel
// / Loop don't exist in @openai/agents — the equivalent is plain TS. The
// only Agent instances are the actual LLM-backed ones (5 of them). The
// "pipeline" is the `research()` function below.
interface ResearchAgents {
  planner: Agent;
  weather: Agent;
  market: Agent;
  critic: Agent;
  synthesist: Agent;
}

function buildAgentGraph(modelFor: ModelFor): ResearchAgents {
  return {
    planner: new Agent({
      name: 'planner_agent',
      instructions: 'Briefly outline what to look up.',
      model: modelFor('planner_agent'),
    }),
    weather: new Agent({
      name: 'weather_agent',
      instructions:
        'Extract a city from the input and call get_weather, then summarize in one sentence.',
      model: modelFor('weather_agent'),
      tools: [getWeather],
    }),
    market: new Agent({
      name: 'market_agent',
      instructions:
        'Extract a ticker from the input and call get_stock_price, then summarize in one sentence.',
      model: modelFor('market_agent'),
      tools: [getStockPrice],
    }),
    critic: new Agent({
      name: 'critic_agent',
      instructions: 'Score the draft 0-1 and suggest one improvement.',
      model: modelFor('critic_agent'),
    }),
    synthesist: new Agent({
      name: 'synthesist_agent',
      instructions:
        'Summarize the weather, the stock price, and the critique.',
      model: modelFor('synthesist_agent'),
    }),
  };
}

// Sequential → Parallel → Loop → Sequential, but hand-rolled. `withTrace`
// pins everything inside this function to a single trace named
// `research_pipeline`, so Weave's Agents view shows the whole workflow as
// one unit instead of five disconnected traces.
async function research(
  agents: ResearchAgents,
  prompt: string
): Promise<string> {
  return await withTrace('research_pipeline', async () => {
    // 1) Plan
    const plan = await run(agents.planner, prompt);

    // 2) Recon: parallel fan-out. Each specialist sees the full prompt and
    // extracts its own slice — the orchestration code doesn't hard-code
    // city/ticker anywhere.
    const [weather, market] = await Promise.all([
      run(agents.weather, prompt),
      run(agents.market, prompt),
    ]);

    // 3) Critique loop: 2 iterations, each a fresh run() of the same
    // critic. Each iteration is its own root invoke_agent within the
    // shared trace.
    let draft = `Plan: ${plan.finalOutput}\nWeather: ${weather.finalOutput}\nMarket: ${market.finalOutput}`;
    let critique = '';
    for (let i = 0; i < 2; i++) {
      const result = await run(
        agents.critic,
        `Iteration ${i + 1}: critique this draft.\n${draft}`
      );
      critique = result.finalOutput ?? '';
      draft = `${draft}\nCritique ${i + 1}: ${critique}`;
    }

    // 4) Synthesize
    const final = await run(
      agents.synthesist,
      `Combine the plan, weather, stock price, and critique into a final summary.\n${draft}`
    );
    return final.finalOutput ?? '';
  });
}

// Complete live usage: init Weave, run the graph, flush spans on the way out.
async function runLive(): Promise<void> {
  await weave.init(WANDB_PROJECT);

  const agents = buildAgentGraph(() => LIVE_MODEL);
  console.log('Agent output:\n' + (await research(agents, PROMPT)));

  await weave.flushOTel(); // short-lived script: flush before exit
  console.log(
    `\n✅ Live run complete. Open the "Agents" view for "${WANDB_PROJECT}" in Weave.`
  );
}

// ╔══════════════════════════════════════════════════════════════════════╗
// ║  END USER CODE.  Everything below is OFFLINE-CHECK SCAFFOLDING ONLY —    ║
// ║  a scripted model, in-memory span capture, a printer, and assertions.   ║
// ║  None of it is needed to use Weave.                                     ║
// ╚══════════════════════════════════════════════════════════════════════╝

// Subclass of the SDK's real OpenAI Responses model that overrides only the
// network seam (`_fetchResponse`) to return canned `Response` objects.
// Everything downstream — `withResponseSpan` wrapping, stashing `_response`
// on `spanData`, building the `ModelResponse` — runs the production code
// path the SDK uses against the live API.
class MockAgent extends OpenAIResponsesModel {
  private turn = 0;
  constructor(private readonly turns: OpenAI.Responses.Response[]) {
    super(new OpenAI({apiKey: 'mock'}), 'mock-model');
  }

  protected async _fetchResponse(
    _request: ModelRequest,
    _stream: false
  ): Promise<OpenAI.Responses.Response> {
    const t = this.turns[this.turn];
    if (!t) {
      throw new Error(`MockAgent: no response for turn ${this.turn}`);
    }
    this.turn += 1;
    return t;
  }
}

// Inline fixture builder for openai Responses-API `Response` objects. Fills
// the long tail of required-but-irrelevant fields (tool_choice, temperature,
// etc.) so the per-turn scripts stay focused on what the test cares about.
function fakeResponse(opts: {
  id: string;
  text?: string;
  toolCalls?: Array<{callId: string; name: string; args: object}>;
  usage?: {input: number; output: number};
}): OpenAI.Responses.Response {
  const output: OpenAI.Responses.ResponseOutputItem[] = [];
  if (opts.text !== undefined) {
    output.push({
      id: `${opts.id}-msg`,
      type: 'message',
      role: 'assistant',
      status: 'completed',
      content: [{type: 'output_text', text: opts.text, annotations: []}],
    });
  }
  for (const tc of opts.toolCalls ?? []) {
    output.push({
      id: `${opts.id}-${tc.callId}`,
      type: 'function_call',
      call_id: tc.callId,
      name: tc.name,
      arguments: JSON.stringify(tc.args),
      status: 'completed',
    });
  }
  const input = opts.usage?.input ?? 0;
  const out = opts.usage?.output ?? 0;
  return {
    object: 'response',
    id: opts.id,
    created_at: 0,
    output_text: opts.text ?? '',
    error: null,
    incomplete_details: null,
    instructions: null,
    metadata: null,
    model: 'gpt-4o-mini',
    output,
    parallel_tool_calls: false,
    temperature: null,
    tool_choice: 'auto',
    tools: [],
    top_p: null,
    status: 'completed',
    usage: {
      input_tokens: input,
      output_tokens: out,
      total_tokens: input + out,
      input_tokens_details: {cached_tokens: 0},
      output_tokens_details: {reasoning_tokens: 0},
    },
  };
}

// Per-agent canned response sequences. Tool-using agents need two turns
// (function call, then final text once the tool result comes back); the
// critic gets a distinct line per loop iteration.
function scriptedModelFor(): ModelFor {
  const llms = new Map<string, MockAgent>([
    [
      'planner_agent',
      new MockAgent([
        fakeResponse({
          id: 'planner-1',
          text: 'Plan: 1) Paris weather 2) AAPL price 3) critique.',
          usage: {input: 12, output: 11},
        }),
      ]),
    ],
    [
      'weather_agent',
      new MockAgent([
        fakeResponse({
          id: 'weather-1',
          toolCalls: [
            {callId: 'call-w', name: 'get_weather', args: {city: 'Paris'}},
          ],
          usage: {input: 10, output: 5},
        }),
        fakeResponse({
          id: 'weather-2',
          text: 'Paris is sunny, about 21°C.',
          usage: {input: 18, output: 7},
        }),
      ]),
    ],
    [
      'market_agent',
      new MockAgent([
        fakeResponse({
          id: 'market-1',
          toolCalls: [
            {callId: 'call-m', name: 'get_stock_price', args: {ticker: 'AAPL'}},
          ],
          usage: {input: 11, output: 5},
        }),
        fakeResponse({
          id: 'market-2',
          text: 'AAPL is trading around $199.98.',
          usage: {input: 19, output: 6},
        }),
      ]),
    ],
    [
      'critic_agent',
      new MockAgent([
        fakeResponse({
          id: 'critic-1',
          text: 'Score 0.7 — add a fallback for rain.',
          usage: {input: 25, output: 10},
        }),
        fakeResponse({
          id: 'critic-2',
          text: 'Score 0.95 — plan looks complete.',
          usage: {input: 27, output: 9},
        }),
      ]),
    ],
    [
      'synthesist_agent',
      new MockAgent([
        fakeResponse({
          id: 'synth-1',
          text: 'Final plan: sunny Paris (~21°C), AAPL ~$199.98; plan looks complete.',
          usage: {input: 22, output: 12},
        }),
      ]),
    ],
  ]);
  return name =>
    llms.get(name) ??
    new MockAgent([fakeResponse({id: 'fallback', text: 'done'})]);
}

const ATTRS_TO_SHOW = [
  'gen_ai.agent.name',
  'gen_ai.request.model',
  'gen_ai.usage.input_tokens',
  'gen_ai.usage.output_tokens',
  'gen_ai.response.finish_reasons',
  'gen_ai.tool.name',
  'gen_ai.tool.call.arguments',
  'gen_ai.tool.call.result',
  'weave.openai_agents.handoff.from_agent',
  'weave.openai_agents.handoff.to_agent',
] as const;

function truncate(value: unknown, max = 90): string {
  const str = typeof value === 'string' ? value : JSON.stringify(value);
  return str.length > max ? `${str.slice(0, max)}…` : str;
}

function printSpanTree(spans: ReadableSpan[]): void {
  const childrenOf = new Map<string | undefined, ReadableSpan[]>();
  for (const span of spans) {
    const siblings = childrenOf.get(span.parentSpanId) ?? [];
    siblings.push(span);
    childrenOf.set(span.parentSpanId, siblings);
  }
  const idsPresent = new Set(spans.map(s => s.spanContext().spanId));
  const roots = spans.filter(
    s => !s.parentSpanId || !idsPresent.has(s.parentSpanId)
  );

  console.log(`\n===== CAPTURED SPAN TREE (${spans.length} spans) =====`);
  const walk = (span: ReadableSpan, depth: number): void => {
    const pad = '  '.repeat(depth);
    const status =
      span.status.code === 2 ? ` [ERROR: ${span.status.message}]` : '';
    console.log(`${pad}• ${span.name}${status}`);
    for (const attr of ATTRS_TO_SHOW) {
      const value = span.attributes[attr];
      if (value !== undefined) {
        console.log(`${pad}    ${attr} = ${truncate(value)}`);
      }
    }
    for (const child of childrenOf.get(span.spanContext().spanId) ?? []) {
      walk(child, depth + 1);
    }
  };
  for (const root of roots) {
    walk(root, 0);
  }
  console.log('==============================================\n');
}

// Asserts the captured spans match the research graph above. Returns
// failures so the caller can set the exit code.
function checkSpans(spans: ReadableSpan[]): string[] {
  const failures: string[] = [];
  const check = (label: string, ok: boolean) => {
    console.log(`${ok ? '  ✓' : '  ✗'} ${label}`);
    if (!ok) failures.push(label);
  };

  const byOp = (op: string) =>
    spans.filter(s => s.attributes['gen_ai.operation.name'] === op);
  const invokes = byOp('invoke_agent');
  const chats = byOp('chat');
  const tools = byOp('execute_tool');

  const invokesByName = (name: string) =>
    invokes.filter(s => s.attributes['gen_ai.agent.name'] === name);

  console.log('Assertions:');

  // Auto-instrumentation: we never called weave.instrumentOpenAIAgents() in
  // this example, so the only way to get spans is for the preload to have
  // patched @openai/agents at import time. If this fails you likely ran
  // without `--import=weave/instrument`.
  check('Weave auto-registered with @openai/agents tracing', spans.length > 0);

  // Code orchestration: 6 top-level `run()` calls inside one `withTrace`.
  // Each run() opens its own root invoke_agent span (TS owns control flow,
  // not the SDK), and `withTrace` ties them all into a single OTel trace.
  // No `research_pipeline`/`recon_team` Agent spans — those are ADK workflow
  // primitives without an @openai/agents equivalent; they live in TS code.
  const rootInvokes = invokes.filter(s => !s.parentSpanId);
  check(
    'six root invoke_agent spans (planner, weather, market, critic×2, synthesist)',
    rootInvokes.length === 6
  );

  // All five LLM-backed agents are visited; the critic twice.
  for (const name of [
    'planner_agent',
    'weather_agent',
    'market_agent',
    'critic_agent',
    'synthesist_agent',
  ]) {
    check(`invoke_agent span for ${name}`, invokesByName(name).length >= 1);
  }
  check(
    'critic_agent invoked twice (one root per loop iteration)',
    invokesByName('critic_agent').length === 2
  );

  // Leaf tool spans for the two specialists.
  const weatherTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'get_weather'
  );
  const stockTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'get_stock_price'
  );
  check(
    'get_weather tool span (args Paris → Sunny)',
    !!weatherTool &&
      String(weatherTool.attributes['gen_ai.tool.call.arguments']).includes(
        'Paris'
      ) &&
      String(weatherTool.attributes['gen_ai.tool.call.result']).includes(
        'Sunny'
      )
  );
  check(
    'get_stock_price tool span (args AAPL → 199.98)',
    !!stockTool &&
      String(stockTool.attributes['gen_ai.tool.call.arguments']).includes(
        'AAPL'
      ) &&
      String(stockTool.attributes['gen_ai.tool.call.result']).includes('199.98')
  );

  // Tool spans parented under their owning agent's invoke_agent span.
  const weatherAgentSpan = invokesByName('weather_agent')[0];
  const marketAgentSpan = invokesByName('market_agent')[0];
  if (weatherTool && weatherAgentSpan) {
    check(
      'get_weather nests under weather_agent',
      weatherTool.parentSpanId === weatherAgentSpan.spanContext().spanId
    );
  }
  if (stockTool && marketAgentSpan) {
    check(
      'get_stock_price nests under market_agent',
      stockTool.parentSpanId === marketAgentSpan.spanContext().spanId
    );
  }

  // No handoffs and no asTool, so no handoff spans and no nested invoke_agent
  // spans either.
  const handoffs = spans.filter(s => s.name.startsWith('handoff '));
  check('no handoff spans (code orchestration)', handoffs.length === 0);

  // Each top-level `run()` opens its own OTel trace today — `withTrace` ties
  // them together at the Agents-SDK trace layer, not at the OTel layer. The
  // groupId from withTrace lands on every span as `gen_ai.conversation.id`,
  // which is what the Agents-tab UI uses to render them as one flow.
  const traceIds = new Set(spans.map(s => s.spanContext().traceId));
  check(
    'one OTel trace per run() (6 total)',
    traceIds.size === 6
  );
  const conversationIds = new Set(
    spans
      .map(s => s.attributes['gen_ai.conversation.id'])
      .filter((v): v is string => typeof v === 'string')
  );
  check(
    'all spans share one gen_ai.conversation.id (withTrace groupId)',
    conversationIds.size === 1
  );

  // Provider tag on invoke_agent spans too (not just chat).
  check(
    'every invoke_agent span tagged openai provider',
    invokes.length > 0 &&
      invokes.every(s => s.attributes['gen_ai.provider.name'] === 'openai')
  );

  // The finish_reasons attribute — exercised by both turn shapes (tool-call
  // turn → 'tool_calls', text-only turn → 'stop').
  const finishReasons = new Set<string>();
  for (const c of chats) {
    const fr = c.attributes['gen_ai.response.finish_reasons'];
    if (Array.isArray(fr)) {
      for (const r of fr as string[]) finishReasons.add(r);
    }
  }
  check(
    'chat spans expose finish_reasons (stop + tool_calls)',
    finishReasons.has('stop') && finishReasons.has('tool_calls')
  );

  // All chat spans tagged with the openai provider.
  check(
    'every chat span tagged openai provider',
    chats.length > 0 &&
      chats.every(s => s.attributes['gen_ai.provider.name'] === 'openai')
  );

  return failures;
}

async function runOffline(): Promise<void> {
  // A dummy key + slashed project keep init fully local (no entity lookup, no
  // auth), and the in-memory processor bypasses the network exporter — so this
  // runs anywhere, no creds.
  process.env.WANDB_API_KEY ??= 'offline-check-dummy-key';
  const exporter = new InMemorySpanExporter();
  await weave.init('offline-check/openai-agents', {
    genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
  });

  const agents = buildAgentGraph(scriptedModelFor()); // same graph as live
  console.log('Agent output:\n' + (await research(agents, PROMPT)));
  await weave.flushOTel();

  const spans = exporter.getFinishedSpans();
  printSpanTree(spans);
  const failures = checkSpans(spans);

  console.log(
    failures.length === 0
      ? '\n✅ OFFLINE CHECK PASSED — span data matches expectations.'
      : `\n❌ ${failures.length} check(s) FAILED:\n - ${failures.join('\n - ')}`
  );
  process.exit(failures.length === 0 ? 0 : 1);
}

(LIVE ? runLive() : runOffline()).catch(error => {
  console.error(error);
  process.exit(1);
});
