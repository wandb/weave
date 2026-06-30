import {OpenAI} from 'openai';

const MODEL = 'gpt-4o-mini';
const openai = new OpenAI();

const SYSTEM_PROMPT =
  'You are a helpful research assistant. Use the available tools to look ' +
  'things up before answering. Keep answers short.';

type Message = OpenAI.Chat.Completions.ChatCompletionMessageParam;

const tools: OpenAI.Chat.Completions.ChatCompletionTool[] = [
  {
    type: 'function',
    function: {
      name: 'get_weather',
      description: 'Get the current weather for a city.',
      parameters: {
        type: 'object',
        properties: {city: {type: 'string'}},
        required: ['city'],
      },
    },
  },
];

function runTool(name: string, args: Record<string, unknown>): string {
  if (name === 'get_weather') {
    return JSON.stringify({city: args.city, tempF: 72, conditions: 'sunny'});
  }
  return JSON.stringify({error: `unknown tool ${name}`});
}

export async function runAgent(
  question: string,
  maxSteps = 6
): Promise<string> {
  const messages: Message[] = [
    {role: 'system', content: SYSTEM_PROMPT},
    {role: 'user', content: question},
  ];

  for (let step = 0; step < maxSteps; step++) {
    const resp = await openai.chat.completions.create({
      model: MODEL,
      messages,
      tools,
    });
    const msg = resp.choices[0].message;
    messages.push(msg);

    if (!msg.tool_calls?.length) {
      return msg.content ?? '';
    }

    for (const tc of msg.tool_calls) {
      const result = runTool(
        tc.function.name,
        JSON.parse(tc.function.arguments)
      );
      messages.push({role: 'tool', tool_call_id: tc.id, content: result});
    }
  }

  return "Sorry, I couldn't finish that within the step limit.";
}
