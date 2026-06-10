/**
 * Tests for the Google ADK (`@google/adk`) integration.
 *
 * The main tests run the real ADK runner (InMemoryRunner + a scripted
 * BaseLlm, no network) so they exercise ADK's actual plugin dispatch — this
 * matters because the integration depends on which callbacks ADK invokes
 * (e.g. ADK 1.2.0 never dispatches plugin agent callbacks). Edge cases that
 * are hard to reach through the runner (streaming partials, synthetic tool
 * keys, dangling-call cleanup) drive the plugin callbacks directly.
 *
 * Note: @google/adk's CJS build does `require("lodash-es")` (an ESM-only
 * package). Node >= 22 allows that via require(esm), but jest's module
 * runtime does not, so the default jest project maps `lodash-es` to its
 * API-identical CJS twin `lodash` (declared as a devDependency). This is a
 * test-only resolution shim — the weave SDK itself does not use lodash.
 */
import * as weave from '../..';
import {
  commonPatchGoogleADK,
  WeaveAdkPlugin,
} from '../../integrations/googleAdk';
import {commonPatchGoogleGenAI} from '../../integrations/googleGenAI';
import {initWithCustomTraceServer} from '../clientMock';
import {Call, InMemoryTraceServer} from '../helpers/inMemoryTraceServer';

import {
  BaseLlm,
  FunctionTool,
  InMemoryRunner,
  LlmAgent,
  SequentialAgent,
  type LlmRequest,
  type LlmResponse,
} from '@google/adk';
import {z} from 'zod';

const TEST_PROJECT = 'test-project';
const TEST_MODEL = 'gemini-test';

/** A BaseLlm that replays a per-call script of responses. */
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
    throw new Error('live connections are not supported in tests');
  }
}

function textResponse(
  text: string,
  usage?: {prompt: number; completion: number}
): LlmResponse {
  return {
    content: {role: 'model', parts: [{text}]},
    turnComplete: true,
    ...(usage
      ? {
          usageMetadata: {
            promptTokenCount: usage.prompt,
            candidatesTokenCount: usage.completion,
            totalTokenCount: usage.prompt + usage.completion,
          },
        }
      : {}),
  } as LlmResponse;
}

function functionCallResponse(
  toolName: string,
  args: Record<string, unknown>,
  usage?: {prompt: number; completion: number}
): LlmResponse {
  return {
    content: {
      role: 'model',
      parts: [{functionCall: {id: 'fc-1', name: toolName, args}}],
    },
    ...(usage
      ? {
          usageMetadata: {
            promptTokenCount: usage.prompt,
            candidatesTokenCount: usage.completion,
            totalTokenCount: usage.prompt + usage.completion,
          },
        }
      : {}),
  } as LlmResponse;
}

function userMessage(text: string) {
  return {role: 'user', parts: [{text}]};
}

async function runToCompletion(
  runner: InMemoryRunner,
  params: {userId: string; sessionId: string; newMessage: any}
) {
  const events = [];
  for await (const event of runner.runAsync(params)) {
    events.push(event);
  }
  return events;
}

function byOp(calls: Call[], opName: string): Call[] {
  return calls.filter(call => call.op_name === opName);
}

describe('Google ADK integration', () => {
  let traceServer: InMemoryTraceServer;

  beforeEach(() => {
    traceServer = new InMemoryTraceServer();
    initWithCustomTraceServer(TEST_PROJECT, traceServer);
  });

  describe('with the real ADK runner', () => {
    test('traces a single-agent tool-using run end to end', async () => {
      const getWeather = new FunctionTool({
        name: 'get_weather',
        description: 'Returns the weather for a city.',
        parameters: z.object({city: z.string()}),
        execute: async ({city}: {city: string}) => ({
          city,
          weather: 'sunny',
        }),
      });

      const model = new ScriptedLlm(TEST_MODEL, [
        [
          functionCallResponse(
            'get_weather',
            {city: 'Paris'},
            {prompt: 10, completion: 5}
          ),
        ],
        [textResponse('It is sunny in Paris.', {prompt: 20, completion: 8})],
      ]);

      const agent = new LlmAgent({
        name: 'weather_agent',
        description: 'Answers weather questions.',
        model,
        tools: [getWeather],
      });

      const runner = new InMemoryRunner({
        agent,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('What is the weather in Paris?'),
      });

      const calls = await traceServer.getCalls(TEST_PROJECT);

      const invocations = byOp(calls, 'google.adk.invocation');
      const agentCalls = byOp(calls, 'google.adk.invoke_agent');
      const llmCalls = byOp(calls, 'google.adk.call_llm');
      const toolCalls = byOp(calls, 'google.adk.execute_tool');

      expect(invocations).toHaveLength(1);
      expect(agentCalls).toHaveLength(1);
      expect(llmCalls).toHaveLength(2);
      expect(toolCalls).toHaveLength(1);

      const [root] = invocations;
      const [agentCall] = agentCalls;
      const [toolCall] = toolCalls;

      // Every call is finished and shares the root's trace.
      for (const call of [
        ...invocations,
        ...agentCalls,
        ...llmCalls,
        ...toolCalls,
      ]) {
        expect(call.ended_at).toBeDefined();
        expect(call.trace_id).toBe(root.trace_id);
      }

      // Structure: root → agent → (llm, llm, tool)
      expect(root.parent_id).toBeNull();
      expect(agentCall.parent_id).toBe(root.id);
      expect(agentCall.display_name).toBe('weather_agent');
      for (const call of [...llmCalls, ...toolCalls]) {
        expect(call.parent_id).toBe(agentCall.id);
      }

      // Root inputs/outputs.
      expect(root.inputs.user_message.parts[0].text).toBe(
        'What is the weather in Paris?'
      );
      expect(root.inputs.app_name).toBe('weave-adk-test');
      expect(JSON.stringify(root.output)).toContain('It is sunny in Paris.');

      // LLM calls carry the request, the response, and per-model usage.
      const firstLlm = llmCalls.find(call =>
        JSON.stringify(call.output).includes('functionCall')
      );
      const secondLlm = llmCalls.find(call =>
        JSON.stringify(call.output).includes('It is sunny in Paris.')
      );
      expect(firstLlm).toBeDefined();
      expect(secondLlm).toBeDefined();
      expect(firstLlm!.display_name).toBe(TEST_MODEL);
      expect(firstLlm!.inputs.model).toBe(TEST_MODEL);
      expect(JSON.stringify(firstLlm!.inputs.contents)).toContain(
        'What is the weather in Paris?'
      );
      expect(firstLlm!.summary.usage[TEST_MODEL]).toMatchObject({
        prompt_tokens: 10,
        completion_tokens: 5,
        total_tokens: 15,
        requests: 1,
      });
      expect(secondLlm!.summary.usage[TEST_MODEL]).toMatchObject({
        prompt_tokens: 20,
        completion_tokens: 8,
        total_tokens: 28,
        requests: 1,
      });

      // Tool call records its args and result.
      expect(toolCall.display_name).toBe('get_weather');
      expect(toolCall.inputs).toMatchObject({city: 'Paris'});
      expect(toolCall.output).toMatchObject({city: 'Paris', weather: 'sunny'});
      expect(toolCall.attributes.adk_function_call_id).toBe('fc-1');
    });

    test('nests sub-agents under workflow agents', async () => {
      const first = new LlmAgent({
        name: 'first_agent',
        description: 'first',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('first done')]]),
      });
      const second = new LlmAgent({
        name: 'second_agent',
        description: 'second',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('second done')]]),
      });
      const pipeline = new SequentialAgent({
        name: 'pipeline',
        description: 'runs both agents',
        subAgents: [first, second],
      });

      const runner = new InMemoryRunner({
        agent: pipeline,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('go'),
      });

      const calls = await traceServer.getCalls(TEST_PROJECT);
      const [root] = byOp(calls, 'google.adk.invocation');
      const agentCalls = byOp(calls, 'google.adk.invoke_agent');
      const llmCalls = byOp(calls, 'google.adk.call_llm');

      // The pipeline agent itself never calls a model or tool, so no call is
      // synthesized for it unless it has activity of its own; both LLM agents
      // nest under it via the agent tree.
      const firstCall = agentCalls.find(c => c.display_name === 'first_agent');
      const secondCall = agentCalls.find(
        c => c.display_name === 'second_agent'
      );
      const pipelineCall = agentCalls.find(c => c.display_name === 'pipeline');
      expect(firstCall).toBeDefined();
      expect(secondCall).toBeDefined();
      expect(pipelineCall).toBeDefined();

      expect(pipelineCall!.parent_id).toBe(root.id);
      expect(firstCall!.parent_id).toBe(pipelineCall!.id);
      expect(secondCall!.parent_id).toBe(pipelineCall!.id);

      expect(llmCalls).toHaveLength(2);
      const llmParents = llmCalls.map(c => c.parent_id).sort();
      expect(llmParents).toEqual([firstCall!.id, secondCall!.id].sort());

      for (const call of calls) {
        expect(call.ended_at).toBeDefined();
      }
    });

    test('records model errors as call exceptions and still closes the run', async () => {
      class ExplodingLlm extends BaseLlm {
        async *generateContentAsync(): AsyncGenerator<LlmResponse, void> {
          throw new Error('model exploded');
        }
        async connect(): Promise<never> {
          throw new Error('not supported');
        }
      }

      const agent = new LlmAgent({
        name: 'fragile_agent',
        description: 'fails',
        model: new ExplodingLlm({model: TEST_MODEL}),
      });
      const runner = new InMemoryRunner({
        agent,
        appName: 'weave-adk-test',
        plugins: [new WeaveAdkPlugin()],
      });
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('boom'),
      });

      const calls = await traceServer.getCalls(TEST_PROJECT);
      const llmCalls = byOp(calls, 'google.adk.call_llm');
      const [root] = byOp(calls, 'google.adk.invocation');

      expect(llmCalls).toHaveLength(1);
      expect(llmCalls[0].exception).toContain('model exploded');
      expect(llmCalls[0].ended_at).toBeDefined();
      expect(root.ended_at).toBeDefined();
    });

    test('auto-registers the plugin when the module hook has run', async () => {
      // Jest's module registry bypasses Module.prototype.require, so the
      // CJS loader hook never fires here; apply the hook function directly.
      // The real loader path is covered by host-app/e2e runs.
      commonPatchGoogleADK(require('@google/adk'));

      const agent = new LlmAgent({
        name: 'auto_agent',
        description: 'auto instrumented',
        model: new ScriptedLlm(TEST_MODEL, [[textResponse('hello')]]),
      });
      // No plugins passed — the patched Runner.prototype.runAsync
      // self-registers the shared Weave plugin.
      const runner = new InMemoryRunner({agent, appName: 'weave-adk-test'});
      const session = await runner.sessionService.createSession({
        appName: 'weave-adk-test',
        userId: 'user-1',
      });

      await runToCompletion(runner, {
        userId: 'user-1',
        sessionId: session.id,
        newMessage: userMessage('hi'),
      });

      expect(runner.pluginManager.getPlugin('weave')).toBeDefined();

      const calls = await traceServer.getCalls(TEST_PROJECT);
      expect(byOp(calls, 'google.adk.invocation')).toHaveLength(1);
      expect(byOp(calls, 'google.adk.call_llm')).toHaveLength(1);
    });
  });

  describe('plugin callback edge cases', () => {
    const INVOCATION_ID = 'inv-1';

    function invocationContext(overrides: Record<string, unknown> = {}) {
      return {
        invocationId: INVOCATION_ID,
        agent: {name: 'agent_a', description: 'test agent'},
        session: {id: 'sess-1', appName: 'app', userId: 'user-1'},
        userContent: userMessage('hello'),
        ...overrides,
      } as any;
    }

    function callbackContext(agentName = 'agent_a') {
      return {invocationId: INVOCATION_ID, agentName} as any;
    }

    test('streaming: partial responses do not close the LLM call', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {model: TEST_MODEL, contents: []},
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext(),
        llmResponse: {
          partial: true,
          content: {role: 'model', parts: [{text: 'It is'}]},
        },
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext(),
        llmResponse: {
          content: {role: 'model', parts: [{text: 'It is sunny.'}]},
          usageMetadata: {
            promptTokenCount: 3,
            candidatesTokenCount: 4,
            totalTokenCount: 7,
          },
        },
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const calls = await traceServer.getCalls(TEST_PROJECT);
      const llmCalls = byOp(calls, 'google.adk.call_llm');
      expect(llmCalls).toHaveLength(1);
      expect(JSON.stringify(llmCalls[0].output)).toContain('It is sunny.');
      expect(llmCalls[0].summary.usage[TEST_MODEL].total_tokens).toBe(7);
    });

    test('tool errors record exceptions; the late afterToolCallback is ignored', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {name: 'fails', description: 'always fails'};
      const toolContext = {
        invocationId: INVOCATION_ID,
        agentName: 'agent_a',
        functionCallId: 'fc-9',
      } as any;

      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeToolCallback({tool, toolArgs: {x: 1}, toolContext});
      await plugin.onToolErrorCallback({
        tool,
        toolArgs: {x: 1},
        toolContext,
        error: new Error('tool failed'),
      });
      // ADK invokes afterToolCallback even after a tool error.
      await plugin.afterToolCallback({
        tool,
        toolArgs: {x: 1},
        toolContext,
        result: null,
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const calls = await traceServer.getCalls(TEST_PROJECT);
      const toolCalls = byOp(calls, 'google.adk.execute_tool');
      expect(toolCalls).toHaveLength(1);
      expect(toolCalls[0].exception).toContain('tool failed');
    });

    test('agents outside the agent tree nest under the innermost open tool call', async () => {
      const plugin = new WeaveAdkPlugin();
      const tool = {name: 'agent_tool', description: 'wraps an agent'};
      const toolContext = {
        invocationId: INVOCATION_ID,
        agentName: 'agent_a',
        functionCallId: 'fc-2',
      } as any;

      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeToolCallback({tool, toolArgs: {}, toolContext});
      // An AgentTool-wrapped agent is not in the root agent's tree.
      await plugin.beforeModelCallback({
        callbackContext: callbackContext('outside_agent'),
        llmRequest: {model: TEST_MODEL, contents: []},
      });
      await plugin.afterModelCallback({
        callbackContext: callbackContext('outside_agent'),
        llmResponse: {content: {role: 'model', parts: [{text: 'ok'}]}},
      });
      await plugin.afterToolCallback({
        tool,
        toolArgs: {},
        toolContext,
        result: {ok: true},
      });
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const calls = await traceServer.getCalls(TEST_PROJECT);
      const toolCall = byOp(calls, 'google.adk.execute_tool')[0];
      const outsideAgent = byOp(calls, 'google.adk.invoke_agent').find(
        call => call.display_name === 'outside_agent'
      );
      expect(outsideAgent).toBeDefined();
      expect(outsideAgent!.parent_id).toBe(toolCall.id);
    });

    test('afterRun closes dangling calls with interrupted status', async () => {
      const plugin = new WeaveAdkPlugin();
      await plugin.beforeRunCallback({
        invocationContext: invocationContext(),
      });
      await plugin.beforeModelCallback({
        callbackContext: callbackContext(),
        llmRequest: {model: TEST_MODEL, contents: []},
      });
      // No afterModelCallback — simulates an aborted run.
      await plugin.afterRunCallback({invocationContext: invocationContext()});

      const calls = await traceServer.getCalls(TEST_PROJECT);
      const llmCalls = byOp(calls, 'google.adk.call_llm');
      expect(llmCalls).toHaveLength(1);
      expect(llmCalls[0].ended_at).toBeDefined();
      expect(llmCalls[0].output).toMatchObject({status: 'interrupted'});

      for (const call of calls) {
        expect(call.ended_at).toBeDefined();
      }
    });

    test('callbacks are safe without an initialized weave client', async () => {
      const {setGlobalClient} = require('../../clientApi');
      setGlobalClient(null);
      try {
        const plugin = new WeaveAdkPlugin();
        await expect(
          plugin.beforeRunCallback({invocationContext: invocationContext()})
        ).resolves.toBeUndefined();
        await expect(
          plugin.beforeModelCallback({
            callbackContext: callbackContext(),
            llmRequest: {model: TEST_MODEL},
          })
        ).resolves.toBeUndefined();
        await expect(
          plugin.afterRunCallback({invocationContext: invocationContext()})
        ).resolves.toBeUndefined();
      } finally {
        initWithCustomTraceServer(TEST_PROJECT, traceServer);
      }
    });
  });

  describe('google genai client exclusion', () => {
    function fakeGenAIExports() {
      class FakeModels {
        async generateContent(..._args: any[]) {
          return {text: 'ok'};
        }
        async generateContentStream(..._args: any[]) {
          return (async function* () {})();
        }
      }
      class FakeGoogleGenAI {
        models: any;
        constructor(public readonly options: any) {
          this.models = new FakeModels();
        }
      }
      return {GoogleGenAI: FakeGoogleGenAI};
    }

    test('ADK-internal clients (x-goog-api-client: google-adk/…) are not wrapped', () => {
      const exports = commonPatchGoogleGenAI(fakeGenAIExports());
      const adkClient = new exports.GoogleGenAI({
        apiKey: 'k',
        httpOptions: {
          headers: {
            'x-goog-api-client': 'google-adk/1.2.0 gl-typescript/v24.0.0',
            'user-agent': 'google-adk/1.2.0 gl-typescript/v24.0.0',
          },
        },
      });
      // Unwrapped: plain models object, no weave op replacement.
      expect(adkClient.models.generateContent.name).toBe('generateContent');

      const userClient = new exports.GoogleGenAI({apiKey: 'k'});
      // Wrapped: generateContent is replaced by a weave op.
      expect(userClient.models.generateContent.name).not.toBe(
        'generateContent'
      );
    });
  });
});
