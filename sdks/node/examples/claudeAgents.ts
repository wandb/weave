/**
 * Example: Claude Agent SDK integration with Weave — one multi-turn session.
 *
 * Demonstrates tracing the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`)
 * with Weave. The SDK's `query()` is automatically instrumented via module
 * loader hooks when you import Weave — no manual setup required.
 *
 * This runs a single conversation as a sequence of follow-up turns. Each turn
 * is its own `query()` call (and its own `invoke_agent` root span), but the
 * follow-ups pass `options.resume` with the first turn's `session_id`, so the
 * SDK continues the same session and the integration stamps the same
 * `gen_ai.conversation.id` on every span. The result: the turns group as one
 * session in the Weave Agents tab, each turn expandable into its
 * `chat` / `execute_tool` children.
 *
 * Requires `@anthropic-ai/claude-agent-sdk` to be installed and a Claude Code
 * auth setup (e.g. `ANTHROPIC_API_KEY`).
 */

import * as weave from 'weave';
import {query, type Options} from '@anthropic-ai/claude-agent-sdk';

// Set your own entity/project name here
const WANDB_PROJECT = process.env.WANDB_PROJECT || 'example';
// Override with e.g. ANTHROPIC_MODEL=claude-opus-4-6
const MODEL = process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-5';

/** Collapse whitespace and clip long strings so the transcript stays readable. */
function clip(text: string, max = 120): string {
  const oneLine = text.replace(/\s+/g, ' ').trim();
  return oneLine.length > max ? `${oneLine.slice(0, max)}…` : oneLine;
}

/** Render a tool_result's content (string or content-block array) as a string. */
function stringifyToolResult(content: string | object | undefined): string {
  if (content == null) return '';
  return typeof content === 'string' ? content : JSON.stringify(content);
}

type TurnResult = {
  sessionId?: string;
  costUsd: number;
  turns: number;
  toolCalls: number;
};

/** Run one conversation turn, printing each streamed message, and return its stats. */
async function runTurn(prompt: string, options: Options): Promise<TurnResult> {
  console.log(`\n=== Turn: ${clip(prompt, 80)} ===`);
  const result: TurnResult = {costUsd: 0, turns: 0, toolCalls: 0};

  for await (const message of query({prompt, options})) {
    switch (message.type) {
      case 'system':
        if (message.subtype === 'init') {
          result.sessionId = message.session_id;
          console.log(
            `[session ${message.session_id}] model=${message.model} ` +
              `tools=${message.tools.length}`
          );
        }
        break;

      case 'assistant':
        for (const block of message.message.content) {
          if (block.type === 'thinking') {
            console.log(`  🤔 ${clip(block.thinking)}`);
          } else if (block.type === 'text') {
            console.log(`  💬 ${clip(block.text)}`);
          } else if (block.type === 'tool_use') {
            result.toolCalls += 1;
            console.log(
              `  🔧 ${block.name}(${clip(JSON.stringify(block.input), 80)})`
            );
          }
        }
        break;

      case 'user':
        if (Array.isArray(message.message.content)) {
          for (const block of message.message.content) {
            if (block.type === 'tool_result') {
              const icon = block.is_error ? '❌' : '✅';
              console.log(
                `  ${icon} tool_result: ${clip(stringifyToolResult(block.content))}`
              );
            }
          }
        }
        break;

      case 'result':
        result.sessionId ??= message.session_id;
        result.costUsd = message.total_cost_usd ?? 0;
        result.turns = message.num_turns ?? 0;
        if (message.subtype === 'success') {
          console.log(`  ✔ ${clip(message.result)}`);
        } else {
          console.log(`  ⚠ ended without success: ${message.subtype}`);
        }
        break;

      default:
        break;
    }
  }

  return result;
}

async function main() {
  await weave.init(WANDB_PROJECT);

  // The Claude Agent SDK is automatically instrumented via module loader hooks
  // when you import Weave — no manual setup required.

  // Restrict the toolset to read-only commands so the example is safe to run
  // anywhere; pin the model and cap each turn's agent loop.
  const baseOptions: Options = {
    model: MODEL,
    maxTurns: 8,
    allowedTools: ['Bash', 'Read', 'Glob', 'Grep'],
    cwd: process.cwd(),
  };

  // A single conversation: an initial ask followed by questions that only make
  // sense given the earlier turns ("those", "what you found").
  const turns = [
    'List the TypeScript files in the current directory.',
    'Of those, which file is the largest, and what is it responsible for?',
    'Summarize what you learned about this project in one sentence.',
  ];

  let sessionId: string | undefined;
  const totals = {costUsd: 0, turns: 0, toolCalls: 0};

  for (const prompt of turns) {
    // First turn starts the session; later turns resume it (same session_id →
    // same gen_ai.conversation.id) so they form one session in the Agents tab.
    const options: Options = sessionId
      ? {...baseOptions, resume: sessionId}
      : baseOptions;

    const turn = await runTurn(prompt, options);
    sessionId ??= turn.sessionId;
    totals.costUsd += turn.costUsd;
    totals.turns += turn.turns;
    totals.toolCalls += turn.toolCalls;
  }

  console.log(
    `\n=== session ${sessionId}: ${turns.length} turns, ` +
      `$${totals.costUsd.toFixed(4)}, ${totals.turns} model turns, ` +
      `${totals.toolCalls} tool calls ===`
  );
  console.log(
    'View the full session (all turns grouped) in the Weave Agents tab.'
  );
}

main().catch(console.error);
