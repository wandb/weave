/**
 * Offline smoke test for the Google ADK integration — no API keys, no
 * network. A scripted BaseLlm stands in for Gemini, and a throwaway local
 * HTTP server stands in for the Weave trace server, recording which
 * endpoints the SDK hits. Verifies auto-instrumentation (no plugin passed)
 * and that spans are exported to the AGENTS OTel endpoint
 * (/agents/otel/v1/traces) and nowhere else. Structural span assertions
 * live in src/__tests__/integrations/googleAdk.test.ts. Exits 0 on
 * success, 1 on failure.
 *
 * Run from sdks/node (build first so `weave` resolves to dist). The
 * `weave/instrument` preload is required for ESM/tsx so the hook is installed
 * before the static `@google/adk` import evaluates:
 *   npm run build && node --import=weave/instrument --import=tsx examples/googleAdkSmoke.ts
 */

import http from 'node:http';
import type {AddressInfo} from 'node:net';

import * as weave from 'weave';
import {
  BaseLlm,
  FunctionTool,
  InMemoryRunner,
  LlmAgent,
  type LlmRequest,
  type LlmResponse,
} from '@google/adk';
import {z} from 'zod';

const PROJECT = 'smoke-entity/smoke-project';
const APP_NAME = 'weave-adk-smoke';
const USER_ID = 'smoke-user';
const MODEL = 'gemini-scripted';
const AGENTS_OTLP_PATH = '/agents/otel/v1/traces';

/** Replays a fixed script: one tool call, then a final answer. */
class ScriptedLlm extends BaseLlm {
  private callIndex = 0;

  async *generateContentAsync(
    _llmRequest: LlmRequest,
    _stream?: boolean
  ): AsyncGenerator<LlmResponse, void> {
    const responses: LlmResponse[] = [
      {
        content: {
          role: 'model',
          parts: [
            {
              functionCall: {
                id: 'fc-1',
                name: 'get_weather',
                args: {city: 'Tokyo'},
              },
            },
          ],
        },
        usageMetadata: {
          promptTokenCount: 10,
          candidatesTokenCount: 5,
          totalTokenCount: 15,
        },
      } as LlmResponse,
      {
        content: {role: 'model', parts: [{text: 'It is humid in Tokyo.'}]},
        turnComplete: true,
        usageMetadata: {
          promptTokenCount: 20,
          candidatesTokenCount: 8,
          totalTokenCount: 28,
        },
      } as LlmResponse,
    ];
    yield responses[Math.min(this.callIndex++, responses.length - 1)];
  }

  async connect(): Promise<never> {
    throw new Error('live connections are not supported in this smoke test');
  }
}

let failures = 0;
function check(condition: boolean, label: string) {
  console.log(`${condition ? '  ✓' : '  ✗ FAIL:'} ${label}`);
  if (!condition) {
    failures++;
  }
}

async function main() {
  // Throwaway trace-server stand-in: record the paths POSTed to.
  const posts: Array<{path: string; bytes: number}> = [];
  const server = http.createServer((req, res) => {
    let bytes = 0;
    req.on('data', chunk => (bytes += chunk.length));
    req.on('end', () => {
      if (req.method === 'POST') {
        posts.push({path: req.url ?? '', bytes});
      }
      res.writeHead(200, {'content-type': 'application/json'});
      res.end('{}');
    });
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = (server.address() as AddressInfo).port;
  process.env.WF_TRACE_SERVER_URL = `http://127.0.0.1:${port}`;
  process.env.WANDB_API_KEY = 'smoke-test-dummy-key';

  // `spanProcessor: 'simple'` keeps the real OTLP exporter (one POST per
  // span, no batch delay) so the smoke exercises the actual wire path.
  await weave.init(PROJECT, {genai: {spanProcessor: 'simple'}});

  const agent = new LlmAgent({
    name: 'weather_agent',
    description: 'Answers weather questions.',
    instruction: 'Use the get_weather tool, then answer.',
    model: new ScriptedLlm({model: MODEL}),
    tools: [
      new FunctionTool({
        name: 'get_weather',
        description: 'Get the weather for a city.',
        parameters: z.object({city: z.string()}),
        execute: async ({city}: {city: string}) => ({city, weather: 'humid'}),
      }),
    ],
  });

  // No plugins passed — auto-instrumentation must register the Weave plugin.
  const runner = new InMemoryRunner({agent, appName: APP_NAME});
  const session = await runner.sessionService.createSession({
    appName: APP_NAME,
    userId: USER_ID,
  });
  for await (const _event of runner.runAsync({
    userId: USER_ID,
    sessionId: session.id,
    newMessage: {role: 'user', parts: [{text: 'Weather in Tokyo?'}]},
  })) {
    // drain events
  }

  await weave.flushOTel();
  server.close();

  console.log('\nVerifying:');
  check(
    runner.pluginManager.getPlugin('weave') != null,
    'runner auto-registered the Weave plugin (no plugins were passed)'
  );

  const agentPosts = posts.filter(post => post.path === AGENTS_OTLP_PATH);
  const otherPosts = posts.filter(post => post.path !== AGENTS_OTLP_PATH);
  check(
    agentPosts.length > 0,
    `spans were POSTed to the agents OTel endpoint (${AGENTS_OTLP_PATH})`
  );
  check(
    agentPosts.every(post => post.bytes > 0),
    'every agents-endpoint POST carried a payload'
  );
  check(
    otherPosts.length === 0,
    `nothing was sent anywhere else (saw: ${
      otherPosts.map(post => post.path).join(', ') || 'none'
    })`
  );

  console.log(
    failures === 0
      ? '\nPASS: Google ADK integration smoke test'
      : `\nFAIL: ${failures} check(s) failed`
  );
  process.exit(failures === 0 ? 0 : 1);
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
