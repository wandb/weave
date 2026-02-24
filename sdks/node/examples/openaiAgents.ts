/**
 * Example: OpenAI Agents Integration with Weave
 *
 * Demonstrates tool usage with the OpenAI Agents SDK and Weave tracing.
 *
 * Since this repository doesn't have @openai/agents, please install it separately.
 */

import * as weave from 'weave';
import {Agent, run, tool} from '@openai/agents';
import type {AgentInputItem} from '@openai/agents';
import {z} from 'zod';

// --- Tools ---

const getWeatherTool = tool({
  name: 'get_weather',
  description: 'Get the current weather for a given city.',
  parameters: z.object({
    city: z.string().describe('The name of the city'),
    unit: z.enum(['celsius', 'fahrenheit']).describe('Temperature unit'),
  }),
  async execute({city, unit}) {
    // Simulated weather data
    const weather: Record<string, {temp: number; condition: string}> = {
      'San Francisco': {temp: 18, condition: 'Foggy'},
      'New York': {temp: 22, condition: 'Sunny'},
      London: {temp: 12, condition: 'Cloudy'},
      Tokyo: {temp: 28, condition: 'Humid'},
    };

    const data = weather[city] ?? {temp: 20, condition: 'Clear'};
    const temp =
      unit === 'fahrenheit' ? Math.round((data.temp * 9) / 5 + 32) : data.temp;
    const unitLabel = unit === 'fahrenheit' ? '°F' : '°C';

    return `${city}: ${data.condition}, ${temp}${unitLabel}`;
  },
});

const calculateTool = tool({
  name: 'calculate',
  description: 'Evaluate a basic arithmetic expression.',
  parameters: z.object({
    expression: z.string().describe('A math expression, e.g. "3 * (4 + 2)"'),
  }),
  execute({expression}) {
    // Restrict to safe arithmetic characters only
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
});

// --- Agent ---

async function main() {
  await weave.init('wandb/csbx');

  // OpenAI Agents is automatically instrumented via module loader hooks when you import Weave.
  // The below function need to be called only for edge cases where automatic instrumentation
  // doesn't work (e.g., dynamic imports, bundlers that bypass hooks).

  // await weave.instrumentOpenAIAgents();

  const agent = new Agent({
    name: 'Assistant',
    instructions:
      'You are a helpful assistant. Use the available tools when appropriate to answer questions accurately.',
    tools: [getWeatherTool, calculateTool],
  });

  const queries = [
    'What is the weather like in Tokyo and San Francisco?',
    'What is (17 * 4) + 93?',
  ];

  let history: AgentInputItem[] = [];
  for (const query of queries) {
    console.log(`\nQuery: ${query}`);
    const result = await run(agent, [
      ...history,
      {role: 'user', content: query},
    ]);
    history = result.history;
    console.log(`Answer: ${result.finalOutput}`);
  }
}

main().catch(console.error);
