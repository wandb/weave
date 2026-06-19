/**
 * Example: Claude Agent SDK integration with Weave
 *
 * Demonstrates tracing the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`)
 * with Weave. The SDK's `query()` is automatically instrumented via module
 * loader hooks when you import Weave — no manual setup required.
 *
 * Each run is emitted as GenAI agent spans (`invoke_agent` / `chat` /
 * `execute_tool`, grouped per session by `gen_ai.conversation.id`) to the
 * `/agents/otel` endpoints and surfaced in the Weave Agents tab.
 *
 * Requires `@anthropic-ai/claude-agent-sdk` to be installed and a Claude Code
 * auth setup (e.g. `ANTHROPIC_API_KEY`).
 */

import * as weave from 'weave';
import {query} from '@anthropic-ai/claude-agent-sdk';

// Set your own entity/project name here
const WANDB_PROJECT = process.env.WANDB_PROJECT || 'example';

async function main() {
  await weave.init(WANDB_PROJECT);

  // The Claude Agent SDK is automatically instrumented via module loader hooks
  // when you import Weave — no manual setup required.

  const prompts = [
    'List the files in the current directory, then briefly summarize what this project does.',
  ];

  for (const prompt of prompts) {
    console.log(`\nPrompt: ${prompt}`);
    for await (const message of query({
      prompt,
      options: {maxTurns: 5},
    })) {
      if (message.type === 'assistant') {
        for (const block of message.message.content) {
          if (block.type === 'text') {
            console.log(`Assistant: ${block.text}`);
          }
        }
      } else if (message.type === 'result') {
        if (message.subtype === 'success') {
          console.log(`Answer: ${message.result}`);
        }
        console.log(
          `Cost: $${message.total_cost_usd}, turns: ${message.num_turns}`
        );
      }
    }
  }
}

main().catch(console.error);
