/**
 * Example: Google ADK (Agent Development Kit) Integration with Weave
 *
 * Demonstrates a tool-using Gemini agent built with @google/adk, traced by
 * Weave. This ESM/tsx example uses Weave's preload hook so the ADK module is
 * patched before static imports evaluate. For environments where the hooks
 * cannot run (e.g. some bundlers), pass the plugin explicitly:
 *
 * ```typescript
 * import {WeaveAdkPlugin} from 'weave';
 * new InMemoryRunner({agent, appName, plugins: [new WeaveAdkPlugin()]});
 * ```
 *
 * Requires GEMINI_API_KEY or GOOGLE_GENAI_API_KEY (or Vertex AI env config)
 * for the Gemini call.
 *
 * Run from sdks/node:
 *   node --import=weave/instrument --import=tsx examples/googleAdkAgent.ts
 *
 * Traces are emitted as GenAI-semconv OTel spans to Weave's agents endpoint
 * and appear in the project's Agents view. Expected shape (one trace per
 * runAsync):
 *   invoke_agent weather_agent             <- user message in, final answer out
 *     invoke_agent weather_agent           <- per-agent span
 *       chat gemini-2.5-flash              <- request/response messages + token usage
 *       execute_tool get_weather x2
 *       chat gemini-2.5-flash              <- final answer
 */

import * as weave from 'weave';
import {FunctionTool, InMemoryRunner, LlmAgent} from '@google/adk';
import {z} from 'zod';

// Set your own entity/project name here
const WANDB_PROJECT = process.env.WANDB_PROJECT || 'examples';

const APP_NAME = 'weave-adk-example';
const USER_ID = 'example-user';
const MODEL = 'gemini-2.5-flash';

// --- Tools ---

const getWeatherTool = new FunctionTool({
  name: 'get_weather',
  description: 'Get the current weather for a given city.',
  parameters: z.object({
    city: z.string().describe('The name of the city'),
  }),
  execute: async ({city}) => {
    // Simulated weather data
    const weather: Record<string, {temp: number; condition: string}> = {
      'San Francisco': {temp: 18, condition: 'Foggy'},
      'New York': {temp: 22, condition: 'Sunny'},
      London: {temp: 12, condition: 'Cloudy'},
      Tokyo: {temp: 28, condition: 'Humid'},
    };
    const data = weather[city] ?? {temp: 20, condition: 'Clear'};
    return {city, condition: data.condition, temperature_c: data.temp};
  },
});

// --- Agent ---

async function main() {
  await weave.init(WANDB_PROJECT);

  const agent = new LlmAgent({
    name: 'weather_agent',
    description: 'Answers questions about the weather.',
    instruction:
      'You answer weather questions. Always use the get_weather tool.',
    model: MODEL,
    tools: [getWeatherTool],
  });

  const runner = new InMemoryRunner({agent, appName: APP_NAME});
  const session = await runner.sessionService.createSession({
    appName: APP_NAME,
    userId: USER_ID,
  });

  for await (const event of runner.runAsync({
    userId: USER_ID,
    sessionId: session.id,
    newMessage: {
      role: 'user',
      parts: [{text: "What's the weather in Tokyo and London?"}],
    },
  })) {
    const text = event.content?.parts
      ?.map(part => part.text)
      .filter(Boolean)
      .join('');
    if (text) {
      console.log(`[${event.author}] ${text}`);
    }
  }

  // Deterministic span flush for short-lived scripts (a beforeExit hook
  // also flushes on natural exit).
  await weave.flushOTel();
}

main().catch(console.error);
