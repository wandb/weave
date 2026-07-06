# Weave

Weave is a library for tracing and monitoring AI applications.

## Installation

You can install Weave via npm:

```bash
npm install weave
```

Ensure you have a wandb API key in ~/.netrc.

Like

```
machine api.wandb.ai
  login user
  password <wandb-api-key>
```

Get your wandb API key from [here](https://wandb.ai/authorize).

## Quickstart

Put this in a file called `main.mjs`:

```typescript
import { randomUUID } from "node:crypto";
import * as weave from "weave";
import { Agent, Runner, tool, type AgentInputItem } from "@openai/agents";
import { z } from "zod";

const wikipediaSearch = tool({
  name: "wikipedia_search",
  description: "Search Wikipedia for a topic and return its title and intro paragraph.",
  parameters: z.object({
    query: z.string().describe("The topic to search for"),
  }),
  async execute({ query }) {
    const url = new URL("https://en.wikipedia.org/w/api.php");
    url.search = new URLSearchParams({
      action: "query",
      generator: "search",
      gsrsearch: query,
      gsrlimit: "1",
      prop: "extracts",
      exintro: "true",
      explaintext: "true",
      format: "json",
    }).toString();

    const response = await fetch(url, { headers: { "User-Agent": "weave-demo" } });
    const data = await response.json();
    const page = Object.values(data.query.pages)[0] as { title: string; extract: string };
    return `${page.title}: ${page.extract}`;
  },
});

async function main() {
  await weave.init("<your-team>/<your-project-name>");

  const agent = new Agent({
    name: "Research assistant",
    instructions:
      "You are a research assistant. Use the wikipedia_search tool to look up " +
      "topics when needed, and cite the article titles you used.",
    tools: [wikipediaSearch],
  });

  const runner = new Runner({ groupId: randomUUID() });

  const questions = [
    "Who founded Anthropic?",
    "What is Claude (the AI assistant)?",
    "Summarize what we discussed in one sentence.",
  ];

  let history: AgentInputItem[] = [];
  for (const question of questions) {
    history.push({ role: "user", content: question });
    console.log(`USER: ${question}`);
    const result = await runner.run(agent, history);
    console.log(`AGENT: ${result.finalOutput}\n`);
    history = result.history;
  }
}

main();
```

and then run

```
node --import=weave/instrument main.mjs
```

## Usage

### Initializing a Project

Before you can start tracing your agent or application, you need to initialize a project.

```typescript
import {init} from 'weave';

// Initialize your project with a unique project name
init('my-awesome-ai-project');
```

### Integrations

W&B Weave traces multi-turn agents built with popular SDKs and harnesses without hand-instrumenting each turn. Install a plugin for your agent harness, or call `weave.init()` in code that uses a supported agent SDK, and Weave autopatches the framework.

Import the library, call `weave.init(...)`, and Weave picks it up. For ESM projects, launch with `node --import=weave/instrument`. See the [agent integration quickstart](https://docs.wandb.ai/weave/agent-integration-quickstart) for the full list of integrations.

#### Agent SDKs

- [OpenAI Agents SDK](https://docs.wandb.ai/weave/guides/integrations/openai_agents) (`@openai/agents`, `@openai/agents-realtime`)
- [Google Agent Development Kit (ADK)](https://docs.wandb.ai/weave/guides/integrations/google_adk) (`@google/adk`)
- [Claude Agent SDK](https://docs.wandb.ai/weave/guides/integrations/claude_agent_sdk) (`@anthropic-ai/claude-agent-sdk`)

#### LLM providers

- [OpenAI](https://docs.wandb.ai/weave/guides/integrations/openai) (`openai`)
- [Anthropic](https://docs.wandb.ai/weave/guides/integrations/anthropic) (`@anthropic-ai/sdk`)
- [Google Gen AI](https://docs.wandb.ai/weave/guides/integrations/google) (`@google/genai`)

#### Custom agents and OpenTelemetry

- [Quickstart: Manually instrument an agent](https://docs.wandb.ai/weave/agent-integration-quickstart#custom-agents-and-opentelemetry)
- [Trace your agents](https://docs.wandb.ai/weave/guides/tracking/tracing)

### Evaluations

```typescript
import {init, op, Dataset, Evaluation} from 'weave';

async function main() {
  await init('weavejsdev-eval6');
  const ds = new Dataset({
    id: 'My Dataset',
    description: 'This is a dataset',
    rows: [
      {name: 'Alice', age: 25},
      {name: 'Bob', age: 30},
      {name: 'Charlie', age: 34},
    ],
  });
  const evaluation = new Evaluation({
    dataset: ds,
    scorers: [
      op(
        (modelOutput: any, datasetItem: any) => modelOutput == datasetItem.age,
        {name: 'isEqual'}
      ),
    ],
  });

  const model = op(async function myModel(input) {
    return input.age;
  });

  const results = await evaluation.evaluate({model});
  console.log(JSON.stringify(results, null, 2));
}

main();
```

### Querying Calls

Use `client.getCalls({...})` with a single options object:

```typescript
const calls = await client.getCalls({
  filter: {op_names: ['my-op']},
  includeCosts: true,
  limit: 50,
});
```

To fetch all calls with default settings, pass an empty object:

```typescript
const calls = await client.getCalls({});
```

#### Upgrade guide

Version 0.13.0 introduces a new signature for getCalls(). getCalls() now supports an object type parameter to specify the call options. The old signature will be deprecated in future releases.

Before:

```typescript
await client.getCalls({op_names: ['my-op']}, true, 100);

await client.getCallsIterator({op_names: ['my-op']}, true, 100);

```

After:

```typescript
await client.getCalls({
  filter: {op_names: ['my-op']},
  includeCosts: true,
  limit: 100,
});

await client.getCallsIterator({
  filter: {op_names: ['my-op']},
  includeCosts: true,
  limit: 100,
});
```

## Configuration

Weave reads API keys from the `.netrc` file located in your home directory. Ensure you have the required API keys configured for seamless integration and tracking.

```
machine api.wandb.ai
  login user
  password <wandb-api-key>
```

Get your wandb API key from [here](https://wandb.ai/authorize).

## License

This project is licensed under the Apache2 License - see the [LICENSE](../../LICENSE) file for details.

