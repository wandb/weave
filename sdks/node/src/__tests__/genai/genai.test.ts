import {
  InMemorySpanExporter,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
import type {
  ChatCompletion,
  ChatCompletionMessageFunctionToolCall,
} from 'openai/resources/chat/completions';
import * as weave from '../../../src';
import {login, type Turn, type Message, type MessagePart} from '../../../src';
import {clearWeaveTracerProvider} from '../../../src/genai/provider';
import {getWandbConfigs} from '../../wandb/settings';
import {spanSnapshot, type SpanSnapshotOpts} from './common';
import {InMemoryTraceServer} from '../helpers/inMemoryTraceServer';
import {initWithCustomTraceServer} from '../clientMock';

let mockResponses: ChatCompletion[] = [];

function mockLlmResponses(...responses: ChatCompletion[]) {
  mockResponses = [...responses];
}

// `created` on a ChatCompletion is Unix *seconds*; OTel's TimeInput
// reads bare numbers as either epoch ms or performance.now() values
// (depending on magnitude). Convert to Date to be unambiguous.
function toDate(resp: ChatCompletion) {
  return new Date(resp.created * 1000);
}

async function callSomeLLM(_args: unknown): Promise<ChatCompletion> {
  const next = mockResponses.shift();
  if (!next) {
    throw new Error('callSomeLLM: no mocked response left');
  }
  return next;
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

function chatCompletion(opts: {
  id: string;
  finishReason: 'tool_calls' | 'stop';
  content?: string;
  toolCalls?: Array<{id: string; name: string; args: object}>;
  usage: {prompt_tokens: number; completion_tokens: number};
  created: Date;
}): ChatCompletion {
  return {
    id: opts.id,
    object: 'chat.completion',
    created: Math.floor(opts.created.getTime() / 1000),
    model: 'gpt-4o-mini',
    choices: [
      {
        index: 0,
        finish_reason: opts.finishReason,
        logprobs: null,
        message: {
          role: 'assistant',
          content: opts.content ?? null,
          refusal: null,
          tool_calls: opts.toolCalls?.map(tc => ({
            id: tc.id,
            type: 'function' as const,
            function: {name: tc.name, arguments: JSON.stringify(tc.args)},
          })),
        },
      },
    ],
    usage: {
      ...opts.usage,
      total_tokens: opts.usage.prompt_tokens + opts.usage.completion_tokens,
    },
  };
}

// Turn 1 — "How warm is Tokyo?"

const TURN1_PLAN_MOCK = chatCompletion({
  id: 'chatcmpl-t1-plan',
  finishReason: 'tool_calls',
  toolCalls: [{id: 'call_t1', name: 'get_weather', args: {city: 'Tokyo'}}],
  usage: {prompt_tokens: 42, completion_tokens: 10},
  created: new Date('2026-05-29T10:00:00.000Z'),
});

const TURN1_ANSWER_MOCK = chatCompletion({
  id: 'chatcmpl-t1-answer',
  finishReason: 'stop',
  content: 'Tokyo is 28°C and humid.',
  usage: {prompt_tokens: 70, completion_tokens: 9},
  created: new Date('2026-05-29T10:00:00.900Z'),
});

// Turn 2 — "What about San Francisco and London?"

const TURN2_PLAN_MOCK = chatCompletion({
  id: 'chatcmpl-t2-plan',
  finishReason: 'tool_calls',
  toolCalls: [
    {id: 'call_t2_sf', name: 'get_weather', args: {city: 'San Francisco'}},
    {id: 'call_t2_ldn', name: 'get_weather', args: {city: 'London'}},
  ],
  usage: {prompt_tokens: 90, completion_tokens: 16},
  created: new Date('2026-05-29T10:00:05.000Z'),
});

const TURN2_ANSWER_MOCK = chatCompletion({
  id: 'chatcmpl-t2-answer',
  finishReason: 'stop',
  content: 'San Francisco is 18°C and foggy. London is 12°C and cloudy.',
  usage: {prompt_tokens: 140, completion_tokens: 18},
  created: new Date('2026-05-29T10:00:05.900Z'),
});

// Turn 3 — "How much warmer is Tokyo than San Francisco?"

const TURN3_PLAN_MOCK = chatCompletion({
  id: 'chatcmpl-t3-plan',
  finishReason: 'tool_calls',
  toolCalls: [
    {id: 'call_t3', name: 'calculate', args: {expression: '28 - 18'}},
  ],
  usage: {prompt_tokens: 170, completion_tokens: 12},
  created: new Date('2026-05-29T10:00:10.000Z'),
});

const TURN3_ANSWER_MOCK = chatCompletion({
  id: 'chatcmpl-t3-answer',
  finishReason: 'stop',
  content: 'Tokyo is 10°C warmer than San Francisco.',
  usage: {prompt_tokens: 200, completion_tokens: 12},
  created: new Date('2026-05-29T10:00:10.900Z'),
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
      messages: llm.inputMessages,
    });
    const choice = resp.choices[0];

    const toolCalls = (choice.message.tool_calls ?? []).filter(
      (tc): tc is ChatCompletionMessageFunctionToolCall =>
        tc.type === 'function'
    );

    const parts: MessagePart[] = [];
    if (choice.message.content) {
      parts.push({type: 'text', content: choice.message.content});
    }
    for (const tc of toolCalls) {
      parts.push({
        type: 'tool_call',
        toolCallId: tc.id,
        toolName: tc.function.name,
        arguments: tc.function.arguments,
      });
    }
    const assistantMessage: Message = {role: 'assistant', parts};
    llm.outputMessages = [assistantMessage];
    llm.record({
      usage: {
        inputTokens: resp.usage?.prompt_tokens,
        outputTokens: resp.usage?.completion_tokens,
      },
    });
    llm.end();
    messages.push(assistantMessage);

    if (toolCalls.length === 0) {
      return choice.message.content ?? '';
    }

    for (const tc of toolCalls) {
      const toolDef = agent.tools.find(t => t.name === tc.function.name);
      if (!toolDef) {
        throw new Error(`unknown tool: ${tc.function.name}`);
      }
      const tool = turn.startTool({
        name: tc.function.name,
        args: tc.function.arguments,
        toolCallId: tc.id,
      });
      try {
        const result = await toolDef.execute(JSON.parse(tc.function.arguments));
        tool.result = JSON.stringify(result);
        tool.end();
        messages.push({
          role: 'tool',
          toolCallId: tc.id,
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
  const session = weave.startSession({agentName: agent.name});
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

  beforeEach(async () => {
    const {apiKey} = getWandbConfigs();
    await login(apiKey ?? '');

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
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.input_tokens": 42,
            "gen_ai.usage.output_tokens": 10,
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
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.input_tokens": 70,
            "gen_ai.usage.output_tokens": 9,
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.input_tokens": 90,
            "gen_ai.usage.output_tokens": 16,
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
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.input_tokens": 140,
            "gen_ai.usage.output_tokens": 18,
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.input_tokens": 170,
            "gen_ai.usage.output_tokens": 12,
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
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"}]},{"role":"tool","toolCallId":"call_t3","content":"\\"28 - 18 = 10\\""}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 10°C warmer than San Francisco."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "some-model",
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 12,
          },
          "endTime": "<timestamp>",
          "startTime": "<timestamp>",
        },
        {
          "attributes": {
            "gen_ai.agent.name": "Reasearch Assistant",
            "gen_ai.conversation.id": "<uuid>",
            "gen_ai.operation.name": "invoke_agent",
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

          const choice = resp.choices[0];
          const toolCalls = (choice.message.tool_calls ?? []).filter(
            (tc): tc is ChatCompletionMessageFunctionToolCall =>
              tc.type === 'function'
          );
          const parts: MessagePart[] = [];
          if (choice.message.content) {
            parts.push({type: 'text', content: choice.message.content});
          }
          for (const tc of toolCalls) {
            parts.push({
              type: 'tool_call',
              toolCallId: tc.id,
              toolName: tc.function.name,
              arguments: tc.function.arguments,
            });
          }
          const assistantMessage: Message = {role: 'assistant', parts};
          llm.outputMessages = [assistantMessage];
          llm.record({
            usage: {
              inputTokens: resp.usage?.prompt_tokens,
              outputTokens: resp.usage?.completion_tokens,
            },
          });
          llm.end({endTime: toDate(resp)});
          messages.push(assistantMessage);

          for (const tc of toolCalls) {
            const toolDef = agent.tools.find(t => t.name === tc.function.name);
            if (!toolDef) {
              throw new Error(`unknown tool: ${tc.function.name}`);
            }
            const tool = turn.startTool({
              name: tc.function.name,
              args: tc.function.arguments,
              toolCallId: tc.id,
              startTime: toDate(resp),
            });
            const result = await toolDef.execute(
              JSON.parse(tc.function.arguments)
            );
            tool.result = JSON.stringify(result);
            tool.end({endTime: toDate(next)});
            messages.push({
              role: 'tool',
              toolCallId: tc.id,
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
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 42,
            "gen_ai.usage.output_tokens": 10,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 70,
            "gen_ai.usage.output_tokens": 9,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 90,
            "gen_ai.usage.output_tokens": 16,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 140,
            "gen_ai.usage.output_tokens": 18,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 170,
            "gen_ai.usage.output_tokens": 12,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"}]},{"role":"tool","toolCallId":"call_t3","content":"\\"28 - 18 = 10\\""}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 10°C warmer than San Francisco."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 12,
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

          const choice = resp.choices[0];
          const toolCalls = (choice.message.tool_calls ?? []).filter(
            (tc): tc is ChatCompletionMessageFunctionToolCall =>
              tc.type === 'function'
          );
          const parts: MessagePart[] = [];
          if (choice.message.content) {
            parts.push({type: 'text', content: choice.message.content});
          }
          for (const tc of toolCalls) {
            parts.push({
              type: 'tool_call',
              toolCallId: tc.id,
              toolName: tc.function.name,
              arguments: tc.function.arguments,
            });
          }
          const assistantMessage: Message = {role: 'assistant', parts};
          llm.outputMessages = [assistantMessage];
          llm.record({
            usage: {
              inputTokens: resp.usage?.prompt_tokens,
              outputTokens: resp.usage?.completion_tokens,
            },
          });
          weave.endLLM({endTime: toDate(resp)});
          messages.push(assistantMessage);

          for (const tc of toolCalls) {
            const toolDef = agent.tools.find(t => t.name === tc.function.name);
            if (!toolDef) {
              throw new Error(`unknown tool: ${tc.function.name}`);
            }
            const tool = weave.startTool({
              name: tc.function.name,
              args: tc.function.arguments,
              toolCallId: tc.id,
              startTime: toDate(resp),
            });
            const result = await toolDef.execute(
              JSON.parse(tc.function.arguments)
            );
            tool.result = JSON.stringify(result);
            tool.end({endTime: toDate(next)});
            messages.push({
              role: 'tool',
              toolCallId: tc.id,
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
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 42,
            "gen_ai.usage.output_tokens": 10,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 70,
            "gen_ai.usage.output_tokens": 9,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 90,
            "gen_ai.usage.output_tokens": 16,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 140,
            "gen_ai.usage.output_tokens": 18,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 170,
            "gen_ai.usage.output_tokens": 12,
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
            "gen_ai.input.messages": "[{"role":"system","content":"You are a research assistant. Use the available tools when appropriate to answer questions accurately."},{"role":"user","content":"How warm is Tokyo?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t1","toolName":"get_weather","arguments":"{\\"city\\":\\"Tokyo\\"}"}]},{"role":"tool","toolCallId":"call_t1","content":"{\\"temp\\":28,\\"condition\\":\\"Humid\\"}"},{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 28°C and humid."}]},{"role":"user","content":"What about San Francisco and London?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t2_sf","toolName":"get_weather","arguments":"{\\"city\\":\\"San Francisco\\"}"},{"type":"tool_call","toolCallId":"call_t2_ldn","toolName":"get_weather","arguments":"{\\"city\\":\\"London\\"}"}]},{"role":"tool","toolCallId":"call_t2_sf","content":"{\\"temp\\":18,\\"condition\\":\\"Foggy\\"}"},{"role":"tool","toolCallId":"call_t2_ldn","content":"{\\"temp\\":12,\\"condition\\":\\"Cloudy\\"}"},{"role":"assistant","parts":[{"type":"text","content":"San Francisco is 18°C and foggy. London is 12°C and cloudy."}]},{"role":"user","content":"How much warmer is Tokyo than San Francisco?"},{"role":"assistant","parts":[{"type":"tool_call","toolCallId":"call_t3","toolName":"calculate","arguments":"{\\"expression\\":\\"28 - 18\\"}"}]},{"role":"tool","toolCallId":"call_t3","content":"\\"28 - 18 = 10\\""}]",
            "gen_ai.operation.name": "chat",
            "gen_ai.output.messages": "[{"role":"assistant","parts":[{"type":"text","content":"Tokyo is 10°C warmer than San Francisco."}]}]",
            "gen_ai.provider.name": "some-provider",
            "gen_ai.request.model": "gpt-4o-mini",
            "gen_ai.usage.input_tokens": 200,
            "gen_ai.usage.output_tokens": 12,
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
