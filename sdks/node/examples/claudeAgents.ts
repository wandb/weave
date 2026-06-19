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
 * This example drives a few multi-step prompts with non-default options and
 * pretty-prints the full streamed transcript — model init, thinking, text,
 * tool calls, tool results, and the final result with usage/cost — so you can
 * see exactly what ends up on the spans.
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
function stringifyToolResult(content: unknown): string {
  if (content == null) return '';
  return typeof content === 'string' ? content : JSON.stringify(content);
}

interface RunStats {
  costUsd: number;
  turns: number;
  durationMs: number;
  toolCalls: number;
}

/** Run one agent prompt, printing each streamed message, and return its stats. */
async function runPrompt(prompt: string, options: Options): Promise<RunStats> {
  console.log(`\n=== Prompt: ${clip(prompt, 80)} ===`);
  const stats: RunStats = {costUsd: 0, turns: 0, durationMs: 0, toolCalls: 0};

  for await (const message of query({prompt, options})) {
    switch (message.type) {
      case 'system':
        if (message.subtype === 'init') {
          console.log(
            `[session ${message.session_id}] model=${message.model} ` +
              `tools=${message.tools.length} cwd=${message.cwd}`
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
            stats.toolCalls += 1;
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
        stats.costUsd = message.total_cost_usd ?? 0;
        stats.turns = message.num_turns ?? 0;
        stats.durationMs = message.duration_ms ?? 0;
        if (message.subtype === 'success') {
          console.log(`  ✔ ${clip(message.result)}`);
        } else {
          console.log(`  ⚠ ended without success: ${message.subtype}`);
        }
        console.log(
          `  (cost $${stats.costUsd.toFixed(4)}, ${stats.turns} turns, ` +
            `${stats.toolCalls} tool calls, ${stats.durationMs}ms)`
        );
        break;

      default:
        break;
    }
  }

  return stats;
}

async function main() {
  await weave.init(WANDB_PROJECT);

  // The Claude Agent SDK is automatically instrumented via module loader hooks
  // when you import Weave — no manual setup required.

  // Non-default options: pin the model, cap the agent loop, and restrict the
  // toolset to read-only commands so the example is safe to run anywhere.
  const options: Options = {
    model: MODEL,
    maxTurns: 8,
    allowedTools: ['Bash', 'Read', 'Glob', 'Grep'],
    cwd: process.cwd(),
  };

  const prompts = [
    'List the files in the current directory, then summarize what this project does in two sentences.',
    'How many TypeScript files are in this directory tree, and which one is the largest?',
  ];

  const totals = {costUsd: 0, turns: 0, toolCalls: 0};
  for (const prompt of prompts) {
    const stats = await runPrompt(prompt, options);
    totals.costUsd += stats.costUsd;
    totals.turns += stats.turns;
    totals.toolCalls += stats.toolCalls;
  }

  console.log(
    `\n=== ${prompts.length} runs: $${totals.costUsd.toFixed(4)}, ` +
      `${totals.turns} turns, ${totals.toolCalls} tool calls ===`
  );
  console.log('View the agent traces in the Weave Agents tab.');
}

main().catch(console.error);
