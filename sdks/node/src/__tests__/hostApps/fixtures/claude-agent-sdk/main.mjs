// Claude Agent SDK ESM host app. Launched via
//   node --import=weave/instrument main.mjs
// (declared in this fixture's package.json `scripts.start`) so the ESM loader
// hook is in place and patches `@anthropic-ai/claude-agent-sdk`'s `query()` as
// it is imported — the same invocation a real ESM consumer uses.
//
// query() is pointed at a fake Claude Code executable (fake-claude-cli.mjs)
// that emits a canned stream-json conversation, so this runs fully offline:
// no API key, no network, no real model call. The integration emits GenAI
// agent spans (invoke_agent / chat / execute_tool) to the `/agents/otel`
// endpoints. Rather than stand up an OTLP receiver, we install a capturing
// span processor via weave.init's `genai.spanProcessor` hook and write the
// finished spans to SPAN_OUTPUT_FILE so the test can assert the real
// end-to-end emission.
//
// Run it by hand from THIS directory (see the sibling note in the test driver);
// `weave`/`--import=weave/instrument` resolves from this package's node_modules,
// not the repo root.
import * as weave from 'weave';
import {SimpleSpanProcessor} from '@opentelemetry/sdk-trace-base';
import {writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {query} from '@anthropic-ai/claude-agent-sdk';

const captured = [];
const captureExporter = {
  export(spans, resultCallback) {
    for (const span of spans) {
      captured.push({
        name: span.name,
        spanId: span.spanContext().spanId,
        parentSpanId: span.parentSpanContext?.spanId,
        traceId: span.spanContext().traceId,
        attributes: span.attributes,
        statusCode: span.status.code,
      });
    }
    resultCallback({code: 0});
  },
  shutdown() {
    return Promise.resolve();
  },
};

await weave.init(process.env.WANDB_PROJECT, {
  // SimpleSpanProcessor exports synchronously on span end, so by the time the
  // query() stream drains, every span is captured.
  genai: {spanProcessor: new SimpleSpanProcessor(captureExporter)},
});

const fakeCli = fileURLToPath(
  new URL('./fake-claude-cli.mjs', import.meta.url)
);

for await (const message of query({
  prompt: 'What files are in this directory?',
  options: {pathToClaudeCodeExecutable: fakeCli, executable: 'node'},
})) {
  console.log(`message: ${message.type}`);
}

writeFileSync(process.env.SPAN_OUTPUT_FILE, JSON.stringify(captured));
