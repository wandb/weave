import {OpenAI} from 'openai';
import * as weave from 'weave';

const MODEL = 'gpt-4o-mini';
const openai = new OpenAI();

// --- Wikipedia tool ---

async function wikipediaSearch({query}: {query: string}): Promise<string> {
  const searchUrl = `https://en.wikipedia.org/w/api.php?action=opensearch&limit=1&format=json&search=${encodeURIComponent(query)}`;
  const searchResp = await fetch(searchUrl);
  const searchData = await searchResp.json();
  const title = searchData?.[1]?.[0];
  if (!title) return `No Wikipedia results for "${query}".`;

  const summaryUrl = `https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(title)}`;
  const summaryResp = await fetch(summaryUrl);
  const summaryData = await summaryResp.json();
  return summaryData.extract ?? `No summary available for "${title}".`;
}

const wikipediaTool: OpenAI.Chat.Completions.ChatCompletionTool = {
  type: 'function',
  function: {
    name: 'wikipedia_search',
    description:
      'Search Wikipedia and return a short summary for the top result.',
    parameters: {
      type: 'object',
      properties: {
        query: {type: 'string', description: 'Search query'},
      },
      required: ['query'],
    },
  },
};

// --- Agent helpers ---

type Message = OpenAI.Chat.Completions.ChatCompletionMessageParam;
type ToolCall = OpenAI.Chat.Completions.ChatCompletionMessageToolCall;

async function callLLM(
  messages: Message[],
  tools?: OpenAI.Chat.Completions.ChatCompletionTool[]
): Promise<OpenAI.Chat.Completions.ChatCompletionMessage> {
  const llm = weave.startLLM({model: MODEL, providerName: 'openai'});
  try {
    const resp = await openai.chat.completions.create({
      model: MODEL,
      messages,
      tools,
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
  userMessage: string
): Promise<string | null> {
  history.push({role: 'user', content: userMessage});

  const turn = weave.startTurn({model: MODEL});
  try {
    let msg = await callLLM(history, [wikipediaTool]);
    history.push(msg);

    while (msg.tool_calls?.length) {
      await executeToolCalls(msg.tool_calls, history);
      msg = await callLLM(history, [wikipediaTool]);
      history.push(msg);
    }

    return msg.content;
  } finally {
    turn.end();
  }
}

async function main() {
  await weave.init('examples');

  const session = weave.startSession({agentName: 'research-bot'});
  try {
    console.log(`session_id = ${session.sessionId}\n`);
    const history: Message[] = [];
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
    session.end();
  }
}

main();
