import {OpenAI} from 'openai';
import * as weave from 'weave';

const MODEL = 'gpt-4o-mini';
const openai = new OpenAI();

// --- Wikipedia tool ---

async function wikipediaSearch({query}: {query: string}): Promise<string> {
  const params = new URLSearchParams({
    action: 'query',
    generator: 'search',
    gsrsearch: query,
    gsrlimit: '1',
    prop: 'extracts',
    exintro: '1',
    explaintext: '1',
    format: 'json',
  });
  const resp = await fetch(`https://en.wikipedia.org/w/api.php?${params}`, {
    headers: {'User-Agent': 'weave-demo'},
  });
  const data = await resp.json();
  const pages = data.query.pages as Record<string, {extract: string}>;
  return Object.values(pages)[0].extract;
}

const wikipediaTool: OpenAI.Chat.Completions.ChatCompletionTool = {
  type: 'function',
  function: {
    name: 'wikipedia_search',
    description: 'Search Wikipedia for a topic and return its intro paragraph.',
    parameters: {
      type: 'object',
      properties: {
        query: {type: 'string'},
      },
      required: ['query'],
    },
  },
};

// --- Agent helpers ---

type Message = OpenAI.Chat.Completions.ChatCompletionMessageParam;
type ToolCall = OpenAI.Chat.Completions.ChatCompletionMessageToolCall;

async function callLLM({
  messages,
  tools,
  userMessage,
}: {
  messages: Message[];
  tools: OpenAI.Chat.Completions.ChatCompletionTool[];
  userMessage?: OpenAI.Chat.Completions.ChatCompletionUserMessageParam;
}): Promise<OpenAI.Chat.Completions.ChatCompletionMessage> {
  const llm = weave.startLLM({model: MODEL, providerName: 'openai'});

  if (userMessage) {
    llm.inputMessages = [
      {role: 'user', content: userMessage.content as string},
    ];
  }

  try {
    const resp = await openai.chat.completions.create({
      model: MODEL,
      messages,
      tools,
      parallel_tool_calls: false,
    });
    const msg = resp.choices[0].message;
    llm.output(msg.content ?? '');
    llm.record({
      usage: {
        inputTokens: resp.usage?.prompt_tokens,
        outputTokens: resp.usage?.completion_tokens,
      },
    });
    return msg;
  } finally {
    llm.end();
  }
}

async function executeToolCalls(
  toolCalls: ToolCall[],
  history: Message[]
): Promise<void> {
  for (const tc of toolCalls) {
    const tool = weave.startTool({
      name: tc.function.name,
      args: tc.function.arguments,
      toolCallId: tc.id,
    });
    try {
      tool.result = await wikipediaSearch(JSON.parse(tc.function.arguments));
      history.push({role: 'tool', tool_call_id: tc.id, content: tool.result!});
    } finally {
      tool.end();
    }
  }
}

async function runTurn(
  history: Message[],
  prompt: string
): Promise<string | null> {
  history.push({role: 'user', content: prompt});

  const turn = weave.startTurn({model: MODEL});
  try {
    let msg = await callLLM({
      userMessage: {role: 'user', content: prompt},
      messages: history,
      tools: [wikipediaTool],
    });
    history.push(msg);

    while (msg.tool_calls?.length) {
      await executeToolCalls(msg.tool_calls, history);
      msg = await callLLM({messages: history, tools: [wikipediaTool]});
      history.push(msg);
    }

    return msg.content;
  } finally {
    turn.end();
  }
}

async function main() {
  await weave.init('examples');

  const conversation = weave.startConversation({agentName: 'research-bot'});
  try {
    console.log(`conversation_id = ${conversation.conversationId}\n`);
    const history: Message[] = [
      {
        role: 'system',
        content:
          'Always use the wikipedia_search tool to look up facts before answering. Do not rely on your own knowledge.',
      },
    ];
    const questions = [
      'List the names of a couple dinosaurs that were carnivores.',
      'List a couple more that were herbivores.',
      'Summarize what we discussed in one sentence.',
    ];
    for (const question of questions) {
      console.log(`USER:  ${question}`);
      const answer = await runTurn(history, question);
      console.log(`AGENT: ${answer}\n`);
    }
  } finally {
    conversation.end();
  }
}

main();
