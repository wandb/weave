/**
 * OpenAI Agents → Weave: a multi-agent example that self-checks offline.
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
import {Agent, OpenAIResponsesModel, Runner, tool} from '@openai/agents';
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
import {randomUUID} from 'crypto';

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

function buildAgentGraph(modelFor: ModelFor): Agent {
  const plannerAgent = new Agent({
    name: 'planner_agent',
    instructions: 'Briefly outline what to look up.',
    model: modelFor('planner_agent'),
  });

  const weatherAgent = new Agent({
    name: 'weather_agent',
    instructions:
      'Extract a city from the input and call get_weather, then summarize in one sentence.',
    model: modelFor('weather_agent'),
    tools: [getWeather],
  });

  const marketAgent = new Agent({
    name: 'market_agent',
    instructions:
      'Extract a ticker from the input and call get_stock_price, then summarize in one sentence.',
    model: modelFor('market_agent'),
    tools: [getStockPrice],
  });

  const reconTeam = new Agent({
    name: 'recon_team',
    instructions:
      'Gather weather and stock information in parallel by calling subagents.',
    model: modelFor('recon_team'),
    tools: [weatherAgent.asTool({}), marketAgent.asTool({})],
  });

  const criticAgent = new Agent({
    name: 'critic_agent',
    instructions: 'Score the draft 0-1 and suggest one improvement.',
    model: modelFor('critic_agent'),
  });

  const synthesistAgent = new Agent({
    name: 'synthesist_agent',
    instructions: 'Summarize the weather, the stock price, and the critique.',
    model: modelFor('synthesist_agent'),
  });

  // asTool by default takes `{input: string}` and feeds the input to the
  // sub-agent as a plain user-role message — that's what produces the
  // duplicate "User" turns in the Agents-tab timeline (the orchestrator's
  // ad-libbed prompt looks like another real user message). Pass a typed
  // `parameters` schema and an `inputBuilder` that formats your own seed
  // message instead, so each sub-agent's seed turn is deliberate phrasing
  // rather than orchestrator improv.
  const researchAgent = new Agent({
    name: 'research_pipeline',
    instructions:
      'Use the tools in order: plan, then gather, then critique, then synthesize. Return the synthesize result as the final answer.',
    model: modelFor('research_pipeline'),
    tools: [
      plannerAgent.asTool({
        toolName: 'plan',
        toolDescription: 'Outline what to research for a given user request.',
        parameters: z.object({
          topic: z.string().describe('the user request to plan around'),
        }),
        inputBuilder: ({params}) =>
          `Outline the research steps needed for: ${params.topic}`,
      }),
      reconTeam.asTool({
        toolName: 'gather',
        toolDescription:
          'Gather weather + market info via specialist sub-agents.',
        parameters: z.object({
          topic: z.string().describe('the topic to gather data for'),
        }),
        inputBuilder: ({params}) =>
          `Gather all relevant data (weather, market) for: ${params.topic}`,
      }),
      criticAgent.asTool({
        toolName: 'critique',
        toolDescription: 'Score and improve a draft.',
        parameters: z.object({
          draft: z.string().describe('the draft to critique'),
        }),
        inputBuilder: ({params}) =>
          `Score this draft 0-1 and suggest one improvement:\n${params.draft}`,
      }),
      synthesistAgent.asTool({
        toolName: 'synthesize',
        toolDescription:
          'Combine gathered notes + critique into a final summary.',
        parameters: z.object({
          material: z.string().describe('the notes to combine'),
        }),
        inputBuilder: ({params}) =>
          `Combine these notes into a final summary:\n${params.material}`,
      }),
    ],
  });

  return researchAgent;
}

async function research(
  agents: Agent,
  prompt: string
): Promise<string | undefined> {
  const runner = new Runner({groupId: randomUUID()});
  const result = await runner.run(agents, prompt);
  return result.finalOutput;
}

// Complete live usage: init Weave, run the graph, flush spans on the way out.
async function runLive(): Promise<void> {
  await weave.init(WANDB_PROJECT);

  const agent = buildAgentGraph(() => LIVE_MODEL);
  console.log('Agent output:\n' + (await research(agent, PROMPT)));

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
      // research_pipeline is the only agent that `runner.run()` invokes
      // directly. Its model walks the pipeline one asTool call per turn:
      // plan → gather → critique → synthesize → final text. Each turn's
      // args match the typed schema we declared on `.asTool({...})`.
      'research_pipeline',
      new MockAgent([
        // Turn 1: plan
        fakeResponse({
          id: 'research-1',
          toolCalls: [
            {
              callId: 'call-plan',
              name: 'plan',
              args: {topic: 'a day in Paris with weather + AAPL price'},
            },
          ],
          usage: {input: 20, output: 8},
        }),
        // Turn 2: gather (after seeing the plan)
        fakeResponse({
          id: 'research-2',
          toolCalls: [
            {
              callId: 'call-gather',
              name: 'gather',
              args: {topic: 'Paris weather and AAPL price'},
            },
          ],
          usage: {input: 50, output: 8},
        }),
        // Turn 3: critique (after seeing the gathered data)
        fakeResponse({
          id: 'research-3',
          toolCalls: [
            {
              callId: 'call-critique',
              name: 'critique',
              args: {
                draft:
                  'Plan: visit Paris. Data: Paris sunny ~21°C; AAPL ~$199.98.',
              },
            },
          ],
          usage: {input: 90, output: 12},
        }),
        // Turn 4: synthesize (after seeing the critique)
        fakeResponse({
          id: 'research-4',
          toolCalls: [
            {
              callId: 'call-synth',
              name: 'synthesize',
              args: {
                material:
                  'Plan + Paris weather + AAPL price + critique combined.',
              },
            },
          ],
          usage: {input: 130, output: 15},
        }),
        // Turn 5: final text (the synthesist result, returned as-is)
        fakeResponse({
          id: 'research-5',
          text: 'Final plan: sunny Paris (~21°C), AAPL ~$199.98; plan looks complete.',
          usage: {input: 160, output: 18},
        }),
      ]),
    ],
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
      'recon_team',
      new MockAgent([
        // recon_team uses asTool (not handoffs) for its specialists, so both
        // can run in one turn via parallel tool calls. The default asTool
        // schema is `{input: string}`, so each call carries a free-form
        // natural-language slice of the gather request.
        fakeResponse({
          id: 'recon-1',
          toolCalls: [
            {
              callId: 'call-wa',
              name: 'weather_agent',
              args: {input: 'Look up the current weather in Paris.'},
            },
            {
              callId: 'call-ma',
              name: 'market_agent',
              args: {input: 'Look up the current AAPL stock price.'},
            },
          ],
          usage: {input: 30, output: 12},
        }),
        // Turn 2: model receives both sub-agent results and writes the
        // combined recon summary.
        fakeResponse({
          id: 'recon-2',
          text: 'Weather: Paris is sunny, ~21°C. Market: AAPL ~$199.98.',
          usage: {input: 60, output: 15},
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

  // ONE top-level run(researchAgent, prompt). research_pipeline walks the
  // pipeline by calling its four asTool children in sequence (plan, gather,
  // critique, synthesize). recon_team in turn calls weather + market as
  // asTool — both run in parallel within one recon turn. asTool nests sub-
  // agent spans under their parent's `execute_tool` and inherits the trace,
  // so only research_pipeline is a root and everything sits in one trace.
  const rootInvokes = invokes.filter(s => !s.parentSpanId);
  check(
    'exactly one root invoke_agent span (research_pipeline)',
    rootInvokes.length === 1 &&
      rootInvokes[0].attributes['gen_ai.agent.name'] === 'research_pipeline'
  );

  // All six named agents are visited via asTool.
  for (const name of [
    'research_pipeline',
    'planner_agent',
    'recon_team',
    'weather_agent',
    'market_agent',
    'critic_agent',
    'synthesist_agent',
  ]) {
    check(`invoke_agent span for ${name}`, invokesByName(name).length >= 1);
  }

  // Typed-schema asTool calls produce execute_tool spans named after the
  // toolName, with structured args (not the default `{input: "..."}`).
  const asToolNames = ['plan', 'gather', 'critique', 'synthesize'];
  for (const name of asToolNames) {
    const toolSpan = tools.find(s => s.attributes['gen_ai.tool.name'] === name);
    check(
      `execute_tool ${name} (typed asTool)`,
      !!toolSpan &&
        typeof toolSpan.attributes['gen_ai.tool.call.arguments'] === 'string'
    );
  }
  // The leaf tools inside weather_agent + market_agent.
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

  // asTool nesting: each sub-agent invoke_agent should sit under its
  // corresponding execute_tool span. The chain goes
  //   research_pipeline
  //     ├ execute_tool plan
  //     │   └ planner_agent
  //     ├ execute_tool gather
  //     │   └ recon_team
  //     │       ├ execute_tool weather_agent
  //     │       │   └ weather_agent
  //     │       └ execute_tool market_agent
  //     │           └ market_agent
  //     ├ execute_tool critique
  //     │   └ critic_agent
  //     └ execute_tool synthesize
  //         └ synthesist_agent
  const researchAgentSpan = invokesByName('research_pipeline')[0];
  const plannerAgentSpan = invokesByName('planner_agent')[0];
  const reconAgentSpan = invokesByName('recon_team')[0];
  const criticAgentSpan = invokesByName('critic_agent')[0];
  const synthesistAgentSpan = invokesByName('synthesist_agent')[0];
  const weatherAgentSpan = invokesByName('weather_agent')[0];
  const marketAgentSpan = invokesByName('market_agent')[0];
  const planTool = tools.find(s => s.attributes['gen_ai.tool.name'] === 'plan');
  const gatherTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'gather'
  );
  const critiqueTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'critique'
  );
  const synthTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'synthesize'
  );
  const weatherSubTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'weather_agent'
  );
  const marketSubTool = tools.find(
    s => s.attributes['gen_ai.tool.name'] === 'market_agent'
  );
  if (plannerAgentSpan && planTool) {
    check(
      'planner_agent nests under execute_tool plan',
      plannerAgentSpan.parentSpanId === planTool.spanContext().spanId
    );
  }
  if (reconAgentSpan && gatherTool) {
    check(
      'recon_team nests under execute_tool gather',
      reconAgentSpan.parentSpanId === gatherTool.spanContext().spanId
    );
  }
  if (weatherAgentSpan && weatherSubTool) {
    check(
      'weather_agent nests under execute_tool weather_agent (asTool)',
      weatherAgentSpan.parentSpanId === weatherSubTool.spanContext().spanId
    );
  }
  if (marketAgentSpan && marketSubTool) {
    check(
      'market_agent nests under execute_tool market_agent (asTool)',
      marketAgentSpan.parentSpanId === marketSubTool.spanContext().spanId
    );
  }
  if (criticAgentSpan && critiqueTool) {
    check(
      'critic_agent nests under execute_tool critique',
      criticAgentSpan.parentSpanId === critiqueTool.spanContext().spanId
    );
  }
  if (synthesistAgentSpan && synthTool) {
    check(
      'synthesist_agent nests under execute_tool synthesize',
      synthesistAgentSpan.parentSpanId === synthTool.spanContext().spanId
    );
  }
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

  // No handoffs in this version — everything is asTool, which doesn't emit
  // handoff spans.
  const handoffs = spans.filter(s => s.name.startsWith('handoff '));
  check('no handoff spans (asTool fan-out everywhere)', handoffs.length === 0);

  // asTool inherits the parent trace, so the entire pipeline lives in a
  // single OTel trace.
  const traceIds = new Set(spans.map(s => s.spanContext().traceId));
  check('single trace (asTool inherits the parent trace)', traceIds.size === 1);

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
