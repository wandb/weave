import {
  readFileSync,
  writeFileSync,
  mkdtempSync,
  symlinkSync,
  rmSync,
  readdirSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

if (!process.argv[2])
  throw new Error(
    "Usage: bun scripts/generate_last_turn_fixtures.ts /path/to/core [--write]"
  );
const core = resolve(process.argv[2]);
const dir = mkdtempSync(join(tmpdir(), "last-turn-frontend-"));
const fixturePath = join(
  import.meta.dir,
  "../tests/trace_server/fixtures/last_turn_frontend.json"
);
const stored = JSON.parse(readFileSync(fixturePath, "utf8"));
process.on("exit", () => rmSync(dir, { recursive: true, force: true }));
const app = join(core, "frontends/app");
symlinkSync(join(app, "node_modules"), join(dir, "node_modules"));
const pages = join(
  app,
  "src/weave/components/PagePanelComponents/Home/Browse3/pages"
);
const hooksPath = join(pages, "ChatView/hooks.ts");
const cellPath = join(
  pages,
  "CallsPage/CallsTableDerivedColumns/LLMChatCompletions.tsx"
);
const importPattern = /import\s[\s\S]*?from\s+['"]([^'"]+)['"];?/g;

// Keep the original function bodies and provider imports. Remove dependencies
// used only by hooks/components outside the pure normalization/rendering path.
const hooks = readFileSync(hooksPath, "utf8").replace(
  importPattern,
  (declaration, path) => {
    if (path.startsWith("./ChatFormats/")) {
      return declaration.replace(path, join(pages, "ChatView", path));
    }
    if (["lodash", "react"].includes(path)) {
      return declaration.replace(path, join(app, "node_modules", path));
    }
    return "";
  }
);
writeFileSync(join(dir, "hooks.ts"), hooks);
const cells = readFileSync(cellPath, "utf8").replace(
  importPattern,
  (declaration, path) => {
    if (path === "react")
      return declaration.replace(path, join(app, "node_modules/react"));
    if (path.endsWith("/ChatView/hooks"))
      return declaration.replace(path, "./hooks");
    return "";
  }
);
writeFileSync(
  join(dir, "cells.tsx"),
  cells +
    `
const Icon = () => null;
const Pill = ({label}) => <span>{label}</span>;
const Tailwind = ({children}) => <>{children}</>;
const Tooltip = ({trigger}) => trigger;
const NotApplicable = () => <span>N/A</span>;
const CellValueWithPopupOver = ({collapsed}) => collapsed;
const ChatMessageRenderer = () => null;
const MessageList = () => null;
export {extractLastMessageChunkFromMessages, extractTextFromMessage};
`
);
const { normalizeChatTraceCall } = await import(join(dir, "hooks.ts"));
const {
  extractLastMessageChunkFromMessages,
  extractTextFromMessage,
} = await import(join(dir, "cells.tsx"));
// This is a proposed search projection of the frontend-selected chunk, not an
// existing frontend scalar. Preserve the real text extractor's block boundaries.
function plainText(node: any): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(plainText).join("");
  if (!node || typeof node !== "object") return "";
  return plainText(node.props?.children);
}
const joinText = (items: any[]) =>
  items.filter((x) => typeof x === "string" && x.length).join("\n");
const contentText = (m: any) => plainText(extractTextFromMessage(m));
const toolText = (m: any) =>
  joinText(
    (m.tool_calls ?? []).map((t: any) =>
      joinText([
        t.function?.name,
        t.function?.arguments,
        t.response && contentText(t.response),
      ])
    )
  );
function projection(chunk: any): string | null {
  if (!chunk) return null;
  if (chunk.type === "single")
    return (
      joinText([contentText(chunk.message), toolText(chunk.message)]) || null
    );
  return (
    joinText([
      ...chunk.invokingToolCallMessages.map(toolText),
      ...chunk.toolResultMessages.map(contentText),
    ]) || null
  );
}

const results = stored.cases.map((fixture: any) => {
  let chunk = null;
  try {
    const { inputs } = normalizeChatTraceCall(
      fixture.raw_call
        ? JSON.parse(fixture.raw_call)
        : structuredClone(fixture.call)
    );
    chunk = extractLastMessageChunkFromMessages(inputs?.messages ?? []);
  } catch (error) {
    if (error instanceof ReferenceError) throw error;
  }
  let expected = null;
  try {
    expected = projection(chunk);
  } catch (error) {
    if (error instanceof ReferenceError) throw error;
  }
  return { ...fixture, expected };
});
const sources = [
  hooksPath,
  cellPath,
  ...readdirSync(join(pages, "ChatView/ChatFormats"), { recursive: true })
    .filter((name: string) => name.endsWith(".ts") && !name.includes(".test."))
    .map((name: string) => join(pages, "ChatView/ChatFormats", name)),
];
const sourceHashes = Object.fromEntries(
  sources
    .sort()
    .map((path) => [
      path.slice(core.length + 1),
      createHash("sha256").update(readFileSync(path)).digest("hex"),
    ])
);
if (process.argv.includes("--write")) {
  const frontendCommit = execFileSync(
    "git",
    ["-c", "core.fsmonitor=false", "rev-parse", "HEAD"],
    { cwd: core, encoding: "utf8" }
  ).trim();
  writeFileSync(
    fixturePath,
    JSON.stringify(
      {
        frontend_commit: frontendCommit,
        source_hashes: sourceHashes,
        cases: results,
      },
      null,
      2
    ) + "\n"
  );
} else if (
  JSON.stringify(results) !== JSON.stringify(stored.cases) ||
  JSON.stringify(sourceHashes) !== JSON.stringify(stored.source_hashes)
) {
  throw new Error(
    "Frontend Last Turn fixtures are stale. Regenerate with --write and run the ClickHouse parity tests."
  );
}
console.log(
  `Verified ${results.length} Last Turn fixtures against the frontend functions.`
);
