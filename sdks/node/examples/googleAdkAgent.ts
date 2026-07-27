/**
 * Google ADK (Agent Development Kit) → Weave: a multi-agent example that
 * self-checks offline.
 *
 * The agent is a nested graph that exercises the ADK features Weave traces —
 * sub-agents, parallel fan-out, a bounded refinement loop, and tool calls:
 *
 *   research_pipeline (Sequential)
 *     ├─ planner_agent    (Llm)
 *     ├─ recon_team       (Parallel)
 *     │    ├─ weather_agent (Llm + get_weather)
 *     │    └─ market_agent  (Llm + get_stock_price)
 *     ├─ critique_loop    (Loop ×2)
 *     │    └─ critic_agent  (Llm)            — 2 iterations → 2 chat turns
 *     └─ synthesist_agent (Llm)              — writes the final summary
 *
 * No plugin is passed to the runner: the `weave/instrument` preload patches
 * ADK's Runner to auto-register the Weave plugin. Tracing ADK is "run with the
 * preload" — nothing in your agent code changes.
 *
 * Modes:
 *   (default)     offline self-check — a scripted model, no creds, no network.
 *                 Spans are captured in-memory and asserted. Exits 0 on
 *                 success, 1 on failure.
 *   WEAVE_LIVE=1  real weave.init() + real Gemini → spans land in the Agents
 *                 view of your Weave project.
 *
 * Run from sdks/node. Build first so `weave` resolves to dist, and use a real
 * Node >= 22 — a `node` that is a Bun shim cannot require() ADK's ESM deps:
 *
 *   npm run build
 *   node --import=weave/instrument --import=tsx examples/googleAdkAgent.ts        # offline
 *   WEAVE_LIVE=1 WANDB_API_KEY=… WANDB_PROJECT=<entity>/<project> GEMINI_API_KEY=… \
 *     node --import=weave/instrument --import=tsx examples/googleAdkAgent.ts      # live
 */

import * as weave from 'weave';
import {
  BaseLlm,
  FunctionTool,
  InMemoryRunner,
  LlmAgent,
  LoopAgent,
  ParallelAgent,
  SequentialAgent,
  type BaseAgent,
  type LlmRequest,
  type LlmResponse,
} from '@google/adk';
import {z} from 'zod';
// Offline span capture only. A custom SpanProcessor is the public seam
// (weave.init({genai: {spanProcessor}})); the OTel test exporter lets the
// offline check read spans back. A live app never imports these.
import {
  InMemorySpanExporter,
  type ReadableSpan,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';

const APP_NAME = 'weave-adk-example';
const USER_ID = 'example-user';
const LIVE_MODEL = 'gemini-2.5-flash';
const PROMPT =
  'Plan a day in Paris: check the weather and the AAPL stock price, then critique the plan.';
const LIVE = !!process.env.WEAVE_LIVE;

// A model resolver is the seam that lets both modes share one graph: live
// returns a model name; the offline check returns a scripted fake per agent.
type ModelFor = (agentName: string) => string | BaseLlm;

// ╔══════════════════════════════════════════════════════════════════════╗
// ║  USER CODE — this is the whole integration. Everything below the        ║
// ║  "END USER CODE" banner is offline-test scaffolding, not part of        ║
// ║  using Weave.                                                           ║
// ╚══════════════════════════════════════════════════════════════════════╝

const getWeather = new FunctionTool({
  name: 'get_weather',
  description: 'Current weather for a city.',
  parameters: z.object({city: z.string().describe('the city to look up')}),
  execute: async ({city}: {city: string}) => ({
    city,
    weather: 'sunny',
    temperature_c: 21,
  }),
});

const getStockPrice = new FunctionTool({
  name: 'get_stock_price',
  description: 'Latest stock price for a ticker.',
  parameters: z.object({ticker: z.string().describe('the ticker symbol')}),
  execute: async ({ticker}: {ticker: string}) => ({
    ticker,
    price_usd: 199.98,
    currency: 'USD',
  }),
});

// A nested agent graph. Workflow agents (Sequential/Parallel/Loop) orchestrate
// their sub-agents directly, so the structure is deterministic.
function buildAgentGraph(modelFor: ModelFor): BaseAgent {
  const plannerAgent = new LlmAgent({
    name: 'planner_agent',
    description: 'Breaks the request into research steps.',
    instruction: 'Briefly outline what to look up.',
    model: modelFor('planner_agent'),
  });

  const weatherAgent = new LlmAgent({
    name: 'weather_agent',
    description: 'Looks up the weather.',
    instruction: 'Call get_weather, then summarize in one sentence.',
    model: modelFor('weather_agent'),
    tools: [getWeather],
  });
  const marketAgent = new LlmAgent({
    name: 'market_agent',
    description: 'Looks up a stock price.',
    instruction: 'Call get_stock_price, then summarize in one sentence.',
    model: modelFor('market_agent'),
    tools: [getStockPrice],
  });
  const reconTeam = new ParallelAgent({
    name: 'recon_team',
    description: 'Gathers weather and market data in parallel.',
    subAgents: [weatherAgent, marketAgent],
  });

  const criticAgent = new LlmAgent({
    name: 'critic_agent',
    description: 'Critiques and refines the plan.',
    instruction: 'Score the draft 0-1 and suggest one improvement.',
    model: modelFor('critic_agent'),
  });
  const critiqueLoop = new LoopAgent({
    name: 'critique_loop',
    description: 'Iteratively refines the plan.',
    subAgents: [criticAgent],
    maxIterations: 2,
  });

  const synthesistAgent = new LlmAgent({
    name: 'synthesist_agent',
    description: 'Writes the final plan from the gathered research.',
    instruction: 'Summarize the weather, the stock price, and the critique.',
    model: modelFor('synthesist_agent'),
  });

  return new SequentialAgent({
    name: 'research_pipeline',
    description: 'Plan, gather (parallel), critique (loop), then synthesize.',
    subAgents: [plannerAgent, reconTeam, critiqueLoop, synthesistAgent],
  });
}

// No plugin is passed: auto-instrumentation (the preload) registers the Weave
// plugin on the runner for you.
function buildRunner(agent: BaseAgent): InMemoryRunner {
  return new InMemoryRunner({agent, appName: APP_NAME});
}

async function runQuery(
  runner: InMemoryRunner,
  sessionId: string
): Promise<string> {
  const out: string[] = [];
  for await (const event of runner.runAsync({
    userId: USER_ID,
    sessionId,
    newMessage: {role: 'user', parts: [{text: PROMPT}]},
  })) {
    const text = event.content?.parts
      ?.map(part => part.text)
      .filter(Boolean)
      .join('');
    if (text) {
      out.push(`[${event.author}] ${text}`);
    }
  }
  return out.join('\n');
}

// Complete live usage: init Weave, run the graph, flush spans on the way out.
async function runLive(): Promise<void> {
  const project = process.env.WANDB_PROJECT || 'examples';
  await weave.init(project);

  const runner = buildRunner(buildAgentGraph(() => LIVE_MODEL));
  const session = await runner.sessionService.createSession({
    appName: APP_NAME,
    userId: USER_ID,
  });
  console.log('Agent output:\n' + (await runQuery(runner, session.id)));

  await weave.flushOTel(); // short-lived script: flush before exit
  console.log(
    `\n✅ Live run complete. Open the "Agents" view for "${project}" in Weave.`
  );
}

// ╔══════════════════════════════════════════════════════════════════════╗
// ║  END USER CODE.  Everything below is OFFLINE-CHECK SCAFFOLDING ONLY —    ║
// ║  a scripted model, in-memory span capture, a printer, and assertions.   ║
// ║  None of it is needed to use Weave.                                     ║
// ╚══════════════════════════════════════════════════════════════════════╝

// A BaseLlm that replays canned responses so the offline run is deterministic
// and needs no API key. (Real usage passes a model *name* to the agents.)
class ScriptedLlm extends BaseLlm {
  private callIndex = 0;
  constructor(
    model: string,
    private readonly script: LlmResponse[][]
  ) {
    super({model});
  }
  async *generateContentAsync(
    _llmRequest: LlmRequest,
    _stream?: boolean
  ): AsyncGenerator<LlmResponse, void> {
    const responses =
      this.script[Math.min(this.callIndex, this.script.length - 1)];
    this.callIndex++;
    for (const response of responses) {
      yield response;
    }
  }
  async connect(): Promise<never> {
    throw new Error('live connections are not supported offline');
  }
}

function textResponse(
  text: string,
  prompt: number,
  completion: number
): LlmResponse {
  return {
    content: {role: 'model', parts: [{text}]},
    turnComplete: true,
    usageMetadata: {
      promptTokenCount: prompt,
      candidatesTokenCount: completion,
      totalTokenCount: prompt + completion,
    },
  } as LlmResponse;
}

function functionCallResponse(
  name: string,
  args: Record<string, unknown>,
  prompt: number,
  completion: number
): LlmResponse {
  return {
    content: {
      role: 'model',
      parts: [{functionCall: {id: `fc-${name}`, name, args}}],
    },
    usageMetadata: {
      promptTokenCount: prompt,
      candidatesTokenCount: completion,
      totalTokenCount: prompt + completion,
    },
  } as LlmResponse;
}

// Per-agent scripts. Tool-using agents need two turns (the function call, then
// the final answer once the tool result comes back); the loop's critic gets a
// distinct line per iteration.
function scriptedModelFor(): ModelFor {
  const scripts: Record<string, LlmResponse[][]> = {
    planner_agent: [
      [
        textResponse(
          'Plan: 1) Paris weather 2) AAPL price 3) critique.',
          12,
          11
        ),
      ],
    ],
    weather_agent: [
      [functionCallResponse('get_weather', {city: 'Paris'}, 10, 5)],
      [textResponse('Paris is sunny, about 21°C.', 18, 7)],
    ],
    market_agent: [
      [functionCallResponse('get_stock_price', {ticker: 'AAPL'}, 11, 5)],
      [textResponse('AAPL is trading around $199.98.', 19, 6)],
    ],
    critic_agent: [
      [textResponse('Score 0.7 — add a fallback for rain.', 25, 10)],
      [textResponse('Score 0.95 — plan looks complete.', 27, 9)],
    ],
    synthesist_agent: [
      [
        textResponse(
          'Final plan: sunny Paris (~21°C), AAPL ~$199.98; plan looks complete.',
          22,
          12
        ),
      ],
    ],
  };
  const llms = new Map<string, ScriptedLlm>();
  for (const [name, script] of Object.entries(scripts)) {
    llms.set(name, new ScriptedLlm(name, script));
  }
  return name =>
    llms.get(name) ?? new ScriptedLlm(name, [[textResponse('done', 1, 1)]]);
}

const ATTRS_TO_SHOW = [
  'gen_ai.agent.name',
  'gen_ai.request.model',
  'gen_ai.usage.total_tokens',
  'gen_ai.tool.name',
  'gen_ai.tool.call.arguments',
  'gen_ai.tool.call.result',
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

// Asserts the captured spans match the graph above. Returns the failures so
// the caller can set the exit code.
function checkSpans(
  spans: ReadableSpan[],
  sessionId: string,
  pluginAutoRegistered: boolean
): string[] {
  const failures: string[] = [];
  const check = (label: string, ok: boolean) => {
    console.log(`${ok ? '  ✓' : '  ✗'} ${label}`);
    if (!ok) {
      failures.push(label);
    }
  };

  const byOp = (op: string) =>
    spans.filter(s => s.attributes['gen_ai.operation.name'] === op);
  const invoke = byOp('invoke_agent');
  const tools = byOp('execute_tool');
  const sid = (s: ReadableSpan) => s.spanContext().spanId;

  const root = invoke.find(s => !s.parentSpanId);
  // Agent span(s) for a given agent name (excludes the no-parent run root).
  const agentByName = (name: string) =>
    invoke.filter(
      s => s.parentSpanId && s.attributes['gen_ai.agent.name'] === name
    );
  const one = (name: string) => agentByName(name)[0];

  console.log('Assertions:');

  // Auto-instrumentation: no plugin was passed, so the preload must have
  // patched the runner to register it. If this fails you likely ran without
  // `--import=weave/instrument`.
  check('runner auto-registered the Weave plugin', pluginAutoRegistered);

  // Run root + named agent spans.
  check(
    'single run-root invoke_agent',
    invoke.filter(s => !s.parentSpanId).length === 1
  );
  check(
    'root is "invoke_agent research_pipeline"',
    root?.name === 'invoke_agent research_pipeline'
  );
  for (const name of [
    'research_pipeline',
    'planner_agent',
    'recon_team',
    'weather_agent',
    'market_agent',
    'critique_loop',
    'critic_agent',
    'synthesist_agent',
  ]) {
    check(`invoke_agent span for ${name}`, agentByName(name).length >= 1);
  }

  // Nesting: leaves → workflow parents → pipeline → run root.
  const pipeline = one('research_pipeline');
  const recon = one('recon_team');
  const loop = one('critique_loop');
  if (root && pipeline) {
    check(
      'research_pipeline nests under run root',
      pipeline.parentSpanId === sid(root)
    );
  }
  if (pipeline) {
    check(
      'planner_agent nests under research_pipeline',
      one('planner_agent')?.parentSpanId === sid(pipeline)
    );
    check(
      'recon_team nests under research_pipeline',
      recon?.parentSpanId === sid(pipeline)
    );
    check(
      'critique_loop nests under research_pipeline',
      loop?.parentSpanId === sid(pipeline)
    );
    check(
      'synthesist_agent nests under research_pipeline',
      one('synthesist_agent')?.parentSpanId === sid(pipeline)
    );
  }
  if (recon) {
    check(
      'weather_agent nests under recon_team',
      one('weather_agent')?.parentSpanId === sid(recon)
    );
    check(
      'market_agent nests under recon_team',
      one('market_agent')?.parentSpanId === sid(recon)
    );
  }

  // Recursion: ADK's LoopAgent re-runs the critic each iteration but brackets
  // the looped sub-agent in a single before/after-agent pair — so the two
  // iterations surface as two `chat` turns under one critic invoke_agent span.
  const criticSpan = one('critic_agent');
  const criticChats = byOp('chat').filter(
    s => s.attributes['gen_ai.agent.name'] === 'critic_agent'
  );
  check(
    'critique_loop produced one critic agent span',
    agentByName('critic_agent').length === 1
  );
  check(
    'critique_loop ran the critic twice (2 chat turns)',
    criticChats.length === 2
  );
  if (criticSpan && loop) {
    check(
      'critic_agent nests under critique_loop',
      criticSpan.parentSpanId === sid(loop)
    );
    check(
      'both critic turns nest under critic_agent',
      criticChats.length > 0 &&
        criticChats.every(c => c.parentSpanId === sid(criticSpan))
    );
  }

  // Tool calls captured with args + results.
  const weatherTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'get_weather'
  );
  const stockTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'get_stock_price'
  );
  check(
    'get_weather tool span (args Paris → sunny)',
    !!weatherTool &&
      String(weatherTool.attributes['gen_ai.tool.call.arguments']).includes(
        'Paris'
      ) &&
      String(weatherTool.attributes['gen_ai.tool.call.result']).includes(
        'sunny'
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
  if (weatherTool) {
    check(
      'get_weather nests under weather_agent',
      weatherTool.parentSpanId === sid(one('weather_agent')!)
    );
  }

  // Cross-cutting attributes.
  check(
    'all spans share the root trace id',
    !!root &&
      spans.every(s => s.spanContext().traceId === root.spanContext().traceId)
  );
  check(
    'every span tags the session + gemini provider',
    spans.length > 0 &&
      spans.every(
        s =>
          s.attributes['gen_ai.conversation.id'] === sessionId &&
          s.attributes['gen_ai.provider.name'] === 'gemini'
      )
  );

  return failures;
}

async function runOffline(): Promise<void> {
  // A dummy key + slashed project keep init fully local (no entity lookup, no
  // auth), and the in-memory processor bypasses the network exporter — so this
  // runs anywhere, no creds.
  process.env.WANDB_API_KEY ??= 'offline-check-dummy-key';
  const exporter = new InMemorySpanExporter();
  await weave.init('offline-check/google-adk', {
    genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
  });

  const runner = buildRunner(buildAgentGraph(scriptedModelFor())); // same graph
  const session = await runner.sessionService.createSession({
    appName: APP_NAME,
    userId: USER_ID,
  });
  console.log('Agent output:\n' + (await runQuery(runner, session.id)));
  await weave.flushOTel();

  const spans = exporter.getFinishedSpans();
  printSpanTree(spans);
  const failures = checkSpans(
    spans,
    session.id,
    runner.pluginManager.getPlugin('weave') != null
  );

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
