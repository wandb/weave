import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
import type {
  Response,
  ResponseFunctionToolCall,
} from 'openai/resources/responses/responses';
import * as weave from '../../../src';
import {type Turn, type Message, type MessagePart} from '../../../src';
import {clearWeaveTracerProvider} from '../../../src/genai/provider';
import {spanSnapshot, type SpanSnapshotOpts} from './common';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';
import {initWithCustomTraceServer} from '../clientMock';
import {openAIResponse} from '../helpers/openaiHelpers';

let mockResponses: Response[] = [];

function mockLlmResponses(...responses: Response[]) {
  mockResponses = [...responses];
}

// `created_at` on a Response is Unix *seconds*; OTel's TimeInput reads
// bare numbers as either epoch ms or performance.now() values (depending
// on magnitude). Convert to Date to be unambiguous.
function toDate(resp: Response) {
  return new Date(resp.created_at * 1000);
}

async function callSomeLLM(_args: unknown): Promise<Response> {
  const next = mockResponses.shift();
  if (!next) {
    throw new Error('callSomeLLM: no mocked response left');
  }
  return next;
}

function extractFromResponse(resp: Response): {
  parts: MessagePart[];
  toolCalls: ResponseFunctionToolCall[];
  reasoning: string;
} {
  const parts: MessagePart[] = [];
  const toolCalls: ResponseFunctionToolCall[] = [];
  let reasoning = '';

  for (const item of resp.output) {
    if (item.type === 'message') {
      for (const c of item.content) {
        if (c.type === 'output_text') {
          parts.push({type: 'text', content: c.text});
        }
      }
    } else if (item.type === 'function_call') {
      toolCalls.push(item);
      parts.push({
        type: 'tool_call',
        toolCallId: item.call_id,
        toolName: item.name,
        arguments: item.arguments,
      });
    } else if (item.type === 'reasoning') {
      const text =
        (item.summary ?? []).map(s => s.text).join('') ||
        (item.content ?? []).map(c => c.text).join('');
      if (text) {
        reasoning += text;
      }
    }
  }

  return {parts, toolCalls, reasoning};
}

type Agent = {
  name: string;
  instructions: string;
  tools: Tool[];
};

type Tool = {
  name: string;
  description: string;
  execute: (args: any) => Promise<unknown> | unknown;
};

const getWeatherTool: Tool = {
  name: 'get_weather',
  description: 'Get the current weather for a given city.',
  execute({city}: {city: string}) {
    switch (city) {
      case 'San Francisco': {
        return {temp: 18, condition: 'Foggy'};
      }

      case 'New York': {
        return {temp: 22, condition: 'Sunny'};
      }

      case 'London': {
        return {temp: 12, condition: 'Cloudy'};
      }

      case 'Tokyo': {
        return {temp: 28, condition: 'Humid'};
      }

      default: {
        throw `Error calling get_weather for ${city}`;
      }
    }
  },
};

const calculateTool: Tool = {
  name: 'calculate',
  description: 'Evaluate a basic arithmetic expression.',
  execute({expression}: {expression: string}) {
    if (!/^[\d\s+\-*/().]+$/.test(expression)) {
      return 'Error: invalid expression';
    }
    try {
      const result = Function(`"use strict"; return (${expression})`)();
      return `${expression} = ${result}`;
    } catch {
      return 'Error: could not evaluate expression';
    }
  },
};

const agent: Agent = {
  name: 'Reasearch Assistant',
  instructions:
    'You are a research assistant. Use the available tools when appropriate to answer questions accurately.',
  tools: [calculateTool, getWeatherTool],
};

// Turn 1 — "How warm is Tokyo?"

const TURN1_PLAN_MOCK = openAIResponse({
  id: 'resp-t1-plan',
  reasoning:
    "The user wants Tokyo's current temperature. I have a `get_weather` " +
    'tool — call it with city="Tokyo" and use the result to answer.',
  toolCalls: [{callId: 'call_t1', name: 'get_weather', args: {city: 'Tokyo'}}],
  usage: {input: 42, output: 10, reasoning: 18},
  createdAt: new Date('2026-05-29T10:00:00.000Z'),
});

const TURN1_ANSWER_MOCK = openAIResponse({
  id: 'resp-t1-answer',
  text: 'Tokyo is 28°C and humid.',
  reasoning:
    'The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, ' +
    'condition Humid. I should phrase the answer concisely.',
  usage: {input: 70, output: 9, reasoning: 24},
  createdAt: new Date('2026-05-29T10:00:00.900Z'),
});

// Turn 2 — "What about San Francisco and London?"

const TURN2_PLAN_MOCK = openAIResponse({
  id: 'resp-t2-plan',
  reasoning:
    'Two independent cities to look up. Issue both `get_weather` calls in ' +
    'parallel — they have no dependency on each other.',
  toolCalls: [
    {callId: 'call_t2_sf', name: 'get_weather', args: {city: 'San Francisco'}},
    {callId: 'call_t2_ldn', name: 'get_weather', args: {city: 'London'}},
  ],
  usage: {input: 90, output: 16, reasoning: 22},
  createdAt: new Date('2026-05-29T10:00:05.000Z'),
});

const TURN2_ANSWER_MOCK = openAIResponse({
  id: 'resp-t2-answer',
  text: 'San Francisco is 18°C and foggy. London is 12°C and cloudy.',
  reasoning:
    'Both tool calls returned successfully. Compose a one-sentence summary ' +
    'covering each city in the order the user named them.',
  usage: {input: 140, output: 18, reasoning: 20},
  createdAt: new Date('2026-05-29T10:00:05.900Z'),
});

// Turn 3 — "How much warmer is Tokyo than San Francisco?"

const TURN3_PLAN_MOCK = openAIResponse({
  id: 'resp-t3-plan',
  reasoning:
    'Conversation history has Tokyo at 28°C (turn 1) and San Francisco at ' +
    '18°C (turn 2). Use the `calculate` tool for "28 - 18" so the answer ' +
    "doesn't rely on the model doing arithmetic.",
  toolCalls: [
    {callId: 'call_t3', name: 'calculate', args: {expression: '28 - 18'}},
  ],
  usage: {input: 170, output: 12, reasoning: 31},
  createdAt: new Date('2026-05-29T10:00:10.000Z'),
});

const TURN3_ANSWER_MOCK = openAIResponse({
  id: 'resp-t3-answer',
  text: 'Tokyo is 10°C warmer than San Francisco.',
  reasoning:
    'Calculator returned 10. State the difference in plain language; ' +
    "include both cities' names so the answer stands on its own.",
  usage: {input: 200, output: 12, reasoning: 19},
  createdAt: new Date('2026-05-29T10:00:10.900Z'),
});

async function runAgentLoop(
  agent: Agent,
  messages: Message[],
  turn: Turn
): Promise<string> {
  const MAX_STEPS = 10;
  for (let i = 0; i < MAX_STEPS; i++) {
    const llm = turn.startLLM({
      model: 'some-model',
      providerName: 'some-provider',
    });
    llm.inputMessages = [...messages];

    const resp = await callSomeLLM({
      model: 'some-model',
      input: llm.inputMessages,
    });
    const {parts, toolCalls, reasoning} = extractFromResponse(resp);

    const assistantMessage: Message = {role: 'assistant', parts};
    if (reasoning) {
      llm.think(reasoning);
    }
    llm.outputMessages = [assistantMessage];
    llm.record({
      usage: {
        inputTokens: resp.usage?.input_tokens,
        outputTokens: resp.usage?.output_tokens,
        reasoningTokens: resp.usage?.output_tokens_details.reasoning_tokens,
        cacheReadInputTokens: resp.usage?.input_tokens_details.cached_tokens,
      },
    });
    llm.end();
    messages.push(assistantMessage);

    if (toolCalls.length === 0) {
      return resp.output_text;
    }

    for (const tc of toolCalls) {
      const toolDef = agent.tools.find(t => t.name === tc.name);
      if (!toolDef) {
        throw new Error(`unknown tool: ${tc.name}`);
      }
      const tool = turn.startTool({
        name: tc.name,
        args: tc.arguments,
        toolCallId: tc.call_id,
      });
      try {
        const result = await toolDef.execute(JSON.parse(tc.arguments));
        tool.result = JSON.stringify(result);
        tool.end();
        messages.push({
          role: 'tool',
          toolCallId: tc.call_id,
          content: tool.result,
        });
      } catch (err) {
        tool.end({error: err as Error});
        throw err;
      }
    }
  }
  throw new Error(`agent did not finish within ${MAX_STEPS} steps`);
}

async function run(agent: Agent, prompts: string[]): Promise<string[]> {
  const session = weave.startSession({
    agentName: agent.name,
    attributes: {
      'myagent.region': 'ORD',
      'myagent.version': '4.21',
    },
  });
  try {
    const messages: Message[] = [{role: 'system', content: agent.instructions}];
    const answers: string[] = [];
    for (const prompt of prompts) {
      messages.push({role: 'user', content: prompt});
      const turn = session.startTurn({agentName: agent.name});
      try {
        answers.push(await runAgentLoop(agent, messages, turn));
      } finally {
        turn.end();
      }
    }
    return answers;
  } finally {
    session.end();
  }
}

describe('GenAI', () => {
  let exporter: InMemorySpanExporter;

  beforeEach(() => {
    // Stub the key the OTel exporter reads; tracing runs through the
    // in-memory server below, so no real backend connection is needed.
    process.env.WANDB_API_KEY = 'test-api-key';

    exporter = new InMemorySpanExporter();

    initWithCustomTraceServer('example', new InMemoryTraceServer(), {
      genai: {spanProcessor: new SimpleSpanProcessor(exporter)},
    });

    clearWeaveTracerProvider();
  });

  async function emittedSpans(opts: SpanSnapshotOpts = {}) {
    await weave.flushOTel();
    const spans = exporter.getFinishedSpans();
    return spans.map(s => spanSnapshot(s, opts));
  }

  test('emits OTel spans for an instrumented agent', async () => {
    mockLlmResponses(
      TURN1_PLAN_MOCK,
      TURN1_ANSWER_MOCK,
      TURN2_PLAN_MOCK,
      TURN2_ANSWER_MOCK,
      TURN3_PLAN_MOCK,
      TURN3_ANSWER_MOCK
    );

    const answers = await run(agent, [
      'How warm is Tokyo?',
      'What about San Francisco and London?',
      'How much warmer is Tokyo than San Francisco?',
    ]);

    expect(answers).toEqual([
      'Tokyo is 28°C and humid.',
      'San Francisco is 18°C and foggy. London is 12°C and cloudy.',
      'Tokyo is 10°C warmer than San Francisco.',
    ]);

    const spans = await emittedSpans();
    expect(spans).toMatchInlineSnapshot(`
      [
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 42,
            "gen_ai.usage.output_tokens": 10,
            "gen_ai.usage.reasoning.output_tokens": 18,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"Tokyo"}",
            "gen_ai.tool.call.id": "call_t1",
            "gen_ai.tool.call.result": "{"temp":28,"condition":"Humid"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 70,
            "gen_ai.usage.output_tokens": 9,
            "gen_ai.usage.reasoning.output_tokens": 24,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 90,
            "gen_ai.usage.output_tokens": 16,
            "gen_ai.usage.reasoning.output_tokens": 22,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"San Francisco"}",
            "gen_ai.tool.call.id": "call_t2_sf",
            "gen_ai.tool.call.result": "{"temp":18,"condition":"Foggy"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"London"}",
            "gen_ai.tool.call.id": "call_t2_ldn",
            "gen_ai.tool.call.result": "{"temp":12,"condition":"Cloudy"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 140,
            "gen_ai.usage.output_tokens": 18,
            "gen_ai.usage.reasoning.output_tokens": 20,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"},{"type":"reasoning","content":"Conversation history has Tokyo at 28°C (turn 1) and San Francisco at 18°C (turn 2). Use the \`calculate\` tool for \\"28 - 18\\" so the answer doesn't rely on the model doing arithmetic."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 170,
            "gen_ai.usage.output_tokens": 12,
            "gen_ai.usage.reasoning.output_tokens": 31,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"expression":"28 - 18"}",
            "gen_ai.tool.call.id": "call_t3",
            "gen_ai.tool.call.result": ""28 - 18 = 10"",
            "gen_ai.tool.name": "calculate",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"},{"type":"reasoning","content":"Conversation history has Tokyo at 28°C (turn 1) and San Francisco at 18°C (turn 2). Use the \`calculate\` tool for \\"28 - 18\\" so the answer doesn't rely on the model doing arithmetic."}]},{"role":"tool","toolCallId":"call_t3","content":"\\"28 - 18 = 10\\""}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 10°C warmer than San Francisco."},{"type":"reasoning","content":"Calculator returned 10. State the difference in plain language; include both cities' names so the answer stands on its own."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 12,
            "gen_ai.usage.reasoning.output_tokens": 19,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
      ]
    `);
  });

  const AGENT_SESSIONS = [
    {
      agentName: agent.name,
      instructions: agent.instructions,
      turns: [
        {
          prompt: 'How warm is Tokyo?',
          startedAt: new Date('2026-05-29T09:59:59.500Z'),
          responses: [TURN1_PLAN_MOCK, TURN1_ANSWER_MOCK],
        },
        {
          prompt: 'What about San Francisco and London?',
          startedAt: new Date('2026-05-29T10:00:04.500Z'),
          responses: [TURN2_PLAN_MOCK, TURN2_ANSWER_MOCK],
        },
        {
          prompt: 'How much warmer is Tokyo than San Francisco?',
          startedAt: new Date('2026-05-29T10:00:09.500Z'),
          responses: [TURN3_PLAN_MOCK, TURN3_ANSWER_MOCK],
        },
      ],
    },
  ];

  // tests backfilling data via our explicit handle-based APIs, eg:
  //
  // const turn = session.startTurn({startTime: '...' });
  // // ...
  // turn.end({endTime: '...'});
  //
  test('allows backfilling data (via handle-based APIs)', async () => {
    for (const recordedSession of AGENT_SESSIONS) {
      const session = weave.startSession({
        agentName: recordedSession.agentName,
        attributes: {
          'myagent.region': 'ORD',
          'myagent.version': '4.21',
        },
      });

      const messages: Message[] = [
        {role: 'system', content: recordedSession.instructions},
      ];
      for (const recordedTurn of recordedSession.turns) {
        const responses = recordedTurn.responses;

        messages.push({role: 'user', content: recordedTurn.prompt});

        const turn = session.startTurn({
          agentName: recordedSession.agentName,
          startTime: recordedTurn.startedAt,
        });

        for (let i = 0; i < responses.length; i++) {
          const resp = responses[i];
          const next = responses[i + 1];

          const llm = turn.startLLM({
            model: resp.model,
            providerName: 'some-provider',
            startTime: toDate(resp),
          });
          llm.inputMessages = [...messages];

          const {parts, toolCalls, reasoning} = extractFromResponse(resp);
          const assistantMessage: Message = {role: 'assistant', parts};
          llm.outputMessages = [assistantMessage];
          if (reasoning) {
            llm.think(reasoning);
          }
          llm.record({
            usage: {
              inputTokens: resp.usage?.input_tokens,
              outputTokens: resp.usage?.output_tokens,
              reasoningTokens:
                resp.usage?.output_tokens_details.reasoning_tokens,
              cacheReadInputTokens:
                resp.usage?.input_tokens_details.cached_tokens,
            },
          });
          llm.end({endTime: toDate(resp)});
          messages.push(assistantMessage);

          for (const tc of toolCalls) {
            const toolDef = agent.tools.find(t => t.name === tc.name);
            if (!toolDef) {
              throw new Error(`unknown tool: ${tc.name}`);
            }
            const tool = turn.startTool({
              name: tc.name,
              args: tc.arguments,
              toolCallId: tc.call_id,
              startTime: toDate(resp),
            });
            const result = await toolDef.execute(JSON.parse(tc.arguments));
            tool.result = JSON.stringify(result);
            tool.end({endTime: toDate(next)});
            messages.push({
              role: 'tool',
              toolCallId: tc.call_id,
              content: tool.result,
            });
          }
        }

        turn.end({endTime: toDate(responses[responses.length - 1])});
      }
      session.end();
    }

    const spans = await emittedSpans({maskTimestamps: false});
    expect(spans).toMatchInlineSnapshot(`
      [
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 42,
            "gen_ai.usage.output_tokens": 10,
            "gen_ai.usage.reasoning.output_tokens": 18,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048800,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"Tokyo"}",
            "gen_ai.tool.call.id": "call_t1",
            "gen_ai.tool.call.result": "{"temp":28,"condition":"Humid"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048800,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 70,
            "gen_ai.usage.output_tokens": 9,
            "gen_ai.usage.reasoning.output_tokens": 24,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048800,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048799,
            500000000,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 90,
            "gen_ai.usage.output_tokens": 16,
            "gen_ai.usage.reasoning.output_tokens": 22,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"San Francisco"}",
            "gen_ai.tool.call.id": "call_t2_sf",
            "gen_ai.tool.call.result": "{"temp":18,"condition":"Foggy"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"London"}",
            "gen_ai.tool.call.id": "call_t2_ldn",
            "gen_ai.tool.call.result": "{"temp":12,"condition":"Cloudy"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 140,
            "gen_ai.usage.output_tokens": 18,
            "gen_ai.usage.reasoning.output_tokens": 20,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048804,
            500000000,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"},{"type":"reasoning","content":"Conversation history has Tokyo at 28°C (turn 1) and San Francisco at 18°C (turn 2). Use the \`calculate\` tool for \\"28 - 18\\" so the answer doesn't rely on the model doing arithmetic."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 170,
            "gen_ai.usage.output_tokens": 12,
            "gen_ai.usage.reasoning.output_tokens": 31,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048810,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"expression":"28 - 18"}",
            "gen_ai.tool.call.id": "call_t3",
            "gen_ai.tool.call.result": ""28 - 18 = 10"",
            "gen_ai.tool.name": "calculate",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048810,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"},{"type":"reasoning","content":"Conversation history has Tokyo at 28°C (turn 1) and San Francisco at 18°C (turn 2). Use the \`calculate\` tool for \\"28 - 18\\" so the answer doesn't rely on the model doing arithmetic."}]},{"role":"tool","toolCallId":"call_t3","content":"\\"28 - 18 = 10\\""}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 10°C warmer than San Francisco."},{"type":"reasoning","content":"Calculator returned 10. State the difference in plain language; include both cities' names so the answer stands on its own."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 12,
            "gen_ai.usage.reasoning.output_tokens": 19,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048810,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048809,
            500000000,
          ],
        },
      ]
    `);
  });

  // tests backfilling data via our top-level context-based APIs, eg:
  //
  // const turn = weave.startTurn({startTime: '...' });
  // // ...
  // weave.endTurn({endTime: '...'});
  //
  test('allows backfilling data (via top-level context-based APIs)', async () => {
    for (const recordedSession of AGENT_SESSIONS) {
      weave.startSession({
        agentName: recordedSession.agentName,
        attributes: {
          'myagent.region': 'ORD',
          'myagent.version': '4.21',
        },
      });

      const messages: Message[] = [
        {role: 'system', content: recordedSession.instructions},
      ];
      for (const recordedTurn of recordedSession.turns) {
        const responses = recordedTurn.responses;

        messages.push({role: 'user', content: recordedTurn.prompt});

        weave.startTurn({
          agentName: recordedSession.agentName,
          startTime: recordedTurn.startedAt,
        });

        for (let i = 0; i < responses.length; i++) {
          const resp = responses[i];
          const next = responses[i + 1];

          const llm = weave.startLLM({
            model: resp.model,
            providerName: 'some-provider',
            startTime: toDate(resp),
          });
          llm.inputMessages = [...messages];

          const {parts, toolCalls, reasoning} = extractFromResponse(resp);
          const assistantMessage: Message = {role: 'assistant', parts};
          llm.outputMessages = [assistantMessage];
          if (reasoning) {
            llm.think(reasoning);
          }
          llm.record({
            usage: {
              inputTokens: resp.usage?.input_tokens,
              outputTokens: resp.usage?.output_tokens,
              reasoningTokens:
                resp.usage?.output_tokens_details.reasoning_tokens,
              cacheReadInputTokens:
                resp.usage?.input_tokens_details.cached_tokens,
            },
          });
          weave.endLLM({endTime: toDate(resp)});
          messages.push(assistantMessage);

          for (const tc of toolCalls) {
            const toolDef = agent.tools.find(t => t.name === tc.name);
            if (!toolDef) {
              throw new Error(`unknown tool: ${tc.name}`);
            }
            const tool = weave.startTool({
              name: tc.name,
              args: tc.arguments,
              toolCallId: tc.call_id,
              startTime: toDate(resp),
            });
            const result = await toolDef.execute(JSON.parse(tc.arguments));
            tool.result = JSON.stringify(result);
            tool.end({endTime: toDate(next)});
            messages.push({
              role: 'tool',
              toolCallId: tc.call_id,
              content: tool.result,
            });
          }
        }

        weave.endTurn({endTime: toDate(responses[responses.length - 1])});
      }
      weave.endSession();
    }

    const spans = await emittedSpans({maskTimestamps: false});
    expect(spans).toMatchInlineSnapshot(`
      [
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 42,
            "gen_ai.usage.output_tokens": 10,
            "gen_ai.usage.reasoning.output_tokens": 18,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048800,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"Tokyo"}",
            "gen_ai.tool.call.id": "call_t1",
            "gen_ai.tool.call.result": "{"temp":28,"condition":"Humid"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048800,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 70,
            "gen_ai.usage.output_tokens": 9,
            "gen_ai.usage.reasoning.output_tokens": 24,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048800,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048800,
            0,
          ],
          "startTime": [
            1780048799,
            500000000,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 90,
            "gen_ai.usage.output_tokens": 16,
            "gen_ai.usage.reasoning.output_tokens": 22,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"San Francisco"}",
            "gen_ai.tool.call.id": "call_t2_sf",
            "gen_ai.tool.call.result": "{"temp":18,"condition":"Foggy"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"city":"London"}",
            "gen_ai.tool.call.id": "call_t2_ldn",
            "gen_ai.tool.call.result": "{"temp":12,"condition":"Cloudy"}",
            "gen_ai.tool.name": "get_weather",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 140,
            "gen_ai.usage.output_tokens": 18,
            "gen_ai.usage.reasoning.output_tokens": 20,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048805,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048805,
            0,
          ],
          "startTime": [
            1780048804,
            500000000,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"},{"type":"reasoning","content":"Conversation history has Tokyo at 28°C (turn 1) and San Francisco at 18°C (turn 2). Use the \`calculate\` tool for \\"28 - 18\\" so the answer doesn't rely on the model doing arithmetic."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 170,
            "gen_ai.usage.output_tokens": 12,
            "gen_ai.usage.reasoning.output_tokens": 31,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048810,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.call.arguments": "{"expression":"28 - 18"}",
            "gen_ai.tool.call.id": "call_t3",
            "gen_ai.tool.call.result": ""28 - 18 = 10"",
            "gen_ai.tool.name": "calculate",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048810,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"},{"type":"reasoning","content":"The user wants Tokyo's current temperature. I have a \`get_weather\` tool — call it with city=\\"Tokyo\\" and use the result to answer."}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."},{"type":"reasoning","content":"The user asked about Tokyo. I called get_weather(Tokyo) and got 28°C, condition Humid. I should phrase the answer concisely."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"},{"type":"reasoning","content":"Two independent cities to look up. Issue both \`get_weather\` calls in parallel — they have no dependency on each other."}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."},{"type":"reasoning","content":"Both tool calls returned successfully. Compose a one-sentence summary covering each city in the order the user named them."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"},{"type":"reasoning","content":"Conversation history has Tokyo at 28°C (turn 1) and San Francisco at 18°C (turn 2). Use the \`calculate\` tool for \\"28 - 18\\" so the answer doesn't rely on the model doing arithmetic."}]},{"role":"tool","toolCallId":"call_t3","content":"\\"28 - 18 = 10\\""}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 10°C warmer than San Francisco."},{"type":"reasoning","content":"Calculator returned 10. State the difference in plain language; include both cities' names so the answer stands on its own."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.cache_read.input_tokens": 0,
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 12,
            "gen_ai.usage.reasoning.output_tokens": 19,
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048810,
            0,
          ],
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
            "myagent.region": "ORD",
            "myagent.version": "4.21",
          },
          "endTime": [
            1780048810,
            0,
          ],
          "startTime": [
            1780048809,
            500000000,
          ],
        },
      ]
    `);
  });
});
