/**
 * Example: Claude Agent SDK integration with Weave — text and images.
 *
 * Demonstrates tracing the Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`)
 * with Weave. The SDK's `query()` is automatically instrumented via module
 * loader hooks when you import Weave — no manual setup required.
 *
 * This runs two independent conversations. The first preserves the original
 * text-only follow-up example. The second sends Claude a base64-encoded image
 * as a native SDK content block and follows up within the same Claude session.
 *
 * Within each conversation, every turn is its own `query()` call (and its own
 * `invoke_agent` root span), while follow-ups pass `options.resume` with the
 * first turn's `session_id`. The integration therefore stamps one shared
 * `gen_ai.conversation.id` on that conversation's spans.
 *
 * Requires `@anthropic-ai/claude-agent-sdk` to be installed and a Claude Code
 * auth setup (e.g. `ANTHROPIC_API_KEY`). Run from `sdks/node` to use the
 * bundled `logs.png`.
 */

import fs from 'fs';
import * as weave from 'weave';
import {
  query,
  type Options,
  type SDKUserMessage,
} from '@anthropic-ai/claude-agent-sdk';

// Set your own entity/project name here
const WANDB_PROJECT = process.env.WANDB_PROJECT || 'example';
// Override with e.g. ANTHROPIC_MODEL=claude-opus-4-6
const MODEL = process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-5';
const IMAGE_PATH = 'logs.png';

type ClaudePrompt = Parameters<typeof query>[0]['prompt'];

type TurnSpec = {
  label: string;
  prompt: ClaudePrompt;
};

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

/** Build the streaming prompt shape required for a native image content block. */
async function* imagePrompt(
  imageBase64: string
): AsyncGenerator<SDKUserMessage> {
  yield {
    type: 'user',
    parent_tool_use_id: null,
    message: {
      role: 'user',
      content: [
        {
          type: 'image',
          source: {
            type: 'base64',
            media_type: 'image/png',
            data: imageBase64,
          },
        },
        {
          type: 'text',
          text: 'Describe this image and call out the most important visual details.',
        },
      ],
    },
  };
}

type TurnResult = {
  sessionId?: string;
  costUsd: number;
  turns: number;
  toolCalls: number;
};

/** Run one conversation turn, printing each streamed message, and return its stats. */
async function runTurn(
  label: string,
  prompt: ClaudePrompt,
  options: Options
): Promise<TurnResult> {
  console.log(`\n=== Turn: ${clip(label, 80)} ===`);
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

/** Run a sequence of resumed queries as one Weave Agents conversation. */
async function runConversation(
  label: string,
  turns: readonly TurnSpec[],
  baseOptions: Options
): Promise<void> {
  console.log(`\n##### ${label} #####`);

  let sessionId: string | undefined;
  const totals = {costUsd: 0, turns: 0, toolCalls: 0};

  for (const turnSpec of turns) {
    // First turn starts the session; later turns resume it (same session_id →
    // same gen_ai.conversation.id) so they form one session in the Agents tab.
    const options: Options = sessionId
      ? {...baseOptions, resume: sessionId}
      : baseOptions;

    const turn = await runTurn(turnSpec.label, turnSpec.prompt, options);
    sessionId ??= turn.sessionId;
    totals.costUsd += turn.costUsd;
    totals.turns += turn.turns;
    totals.toolCalls += turn.toolCalls;
  }

  console.log(
    `\n=== ${label}: session ${sessionId}, ${turns.length} turns, ` +
      `$${totals.costUsd.toFixed(4)}, ${totals.turns} model turns, ` +
      `${totals.toolCalls} tool calls ===`
  );
}

async function main() {
  await weave.init(WANDB_PROJECT);

  // The Claude Agent SDK is automatically instrumented via module loader hooks
  // when you import Weave — no manual setup required.

  // Restrict the toolset to read-only commands so the example is safe to run
  // anywhere; allowedTools auto-approves that same set. Pin the model and cap
  // each turn's agent loop.
  const readOnlyTools = ['Bash', 'Read', 'Glob', 'Grep'];
  const baseOptions: Options = {
    model: MODEL,
    maxTurns: 8,
    tools: readOnlyTools,
    allowedTools: readOnlyTools,
    cwd: process.cwd(),
  };

  // The original text-only example remains useful as the minimal multi-turn
  // path: each follow-up relies on the preceding response.
  const turns = [
    'List the TypeScript files in the current directory.',
    'Of those, which file is the largest, and what is it responsible for?',
    'Summarize what you learned about this project in one sentence.',
  ];
  await runConversation(
    'Original text-only conversation',
    turns.map(prompt => ({label: prompt, prompt})),
    baseOptions
  );

  const imageBase64 = fs.readFileSync(IMAGE_PATH, 'base64');
  const imageSummaryPrompt =
    'Summarize the most important visual detail in one sentence.';
  const imageTurns: TurnSpec[] = [
    {
      label: `Analyze image: ${IMAGE_PATH}`,
      prompt: imagePrompt(imageBase64),
    },
    {
      label: imageSummaryPrompt,
      prompt: imageSummaryPrompt,
    },
  ];
  await runConversation('Image conversation', imageTurns, baseOptions);

  console.log(
    '\nView both sessions (with their turns grouped) in the Weave Agents tab.'
  );
}

main().catch(console.error);
