/**
 * Example: OpenAI Agents Realtime with Weave
 *
 * Demonstrates a voice agent using RealtimeAgent + RealtimeSession with a tool
 * and Weave tracing. Sends a text message and logs the assistant's response.
 *
 * Run:
 *   npm install
 *   npx tsc && node dist/index.js
 *
 * Requires: OPENAI_API_KEY and WANDB_API_KEY env vars
 *
 * Since this repository doesn't have @openai/agents, please install it separately.
 */

import * as weave from 'weave';
import {RealtimeAgent, RealtimeSession, tool} from '@openai/agents/realtime';
import {z} from 'zod';

// Set your own entity/project name here
const WANDB_PROJECT = process.env.WANDB_PROJECT || 'example';

// --- Tool ---

const getWeatherTool = tool({
  name: 'get_weather',
  description: 'Get the current weather for a given city.',
  parameters: z.object({
    city: z.string().describe('The name of the city'),
  }),
  async execute({city}) {
    // Simulated weather data
    const weather: Record<string, string> = {
      'San Francisco': '65°F, foggy',
      'New York': '72°F, sunny',
      London: '55°F, cloudy',
    };
    return weather[city] ?? '70°F, clear';
  },
});

// --- Agent ---

const agent = new RealtimeAgent({
  name: 'Assistant',
  instructions:
    'You are a helpful voice assistant. Keep responses concise — this is a voice conversation.',
  tools: [getWeatherTool],
});

// --- Main ---

async function main() {
  await weave.init(WANDB_PROJECT);

  // @openai/agents-realtime is automatically instrumented via module loader hooks when you
  // import Weave. The below function needs to be called only for edge cases where automatic
  // instrumentation doesn't work (e.g., dynamic imports, bundlers that bypass hooks).

  // weave.patchRealtimeSession();

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error('OPENAI_API_KEY is required');

  const session = new RealtimeSession(agent);

  session.on('history_updated', history => {
    const last = history[history.length - 1];
    if (last?.type === 'message' && last.role === 'assistant') {
      const text = (last.content ?? [])
        .filter((c: any) => c.type === 'output_text')
        .map((c: any) => c.text)
        .join('');
      if (text) console.log(`\nAssistant: ${text}`);
    }
  });

  session.on('error', event => {
    console.error('[error]', event.error);
  });

  console.log('Connecting...');
  await session.connect({apiKey});
  console.log('Connected.');

  session.sendMessage('What is the weather like in San Francisco?');

  // Wait for the response, then disconnect
  await new Promise<void>(resolve => setTimeout(resolve, 10_000));

  session.close();
  console.log('\nDone.');
}

main().catch(console.error);
