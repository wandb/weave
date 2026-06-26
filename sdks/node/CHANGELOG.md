# Changelog

All notable changes to the Weave TypeScript SDK will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.16.0] - 2026-06-26

### Added

- New `@anthropic-ai/claude-agent-sdk` OTel-based integration. ([#7245](https://github.com/wandb/weave/pull/7245))
- New `@google/adk` OTel-based integration.
  - Add basic scaffolding ([#7301](https://github.com/wandb/weave/pull/7301))
  - Add model/`chat` span tracing ([#7302](https://github.com/wandb/weave/pull/7302))
  - Add tool/`execute_tool` span tracing ([#7303](https://github.com/wandb/weave/pull/7303))
  - Add nested Agent span support ([#7305](https://github.com/wandb/weave/pull/7305))
  - Add autoinstrumentation ([#7306](https://github.com/wandb/weave/pull/7306))
- Updated `@openai/agents` integration to default to OTel, with option to revert back to calls-based tracing.
  - Emit `invoke_agent` spans ([#7085](https://github.com/wandb/weave/pull/7085))
  - Emit `execute_tool` spans ([#7086](https://github.com/wandb/weave/pull/7086))
  - Emit `chat` spans ([#7087](https://github.com/wandb/weave/pull/7087))
  - Emit message data on `chat` spans ([#7089](https://github.com/wandb/weave/pull/7089))
  - Emit `handoff`, `guardrail`, `transcription`, `speech`, `speech_group`, `mcp_list_tools`, and custom spans ([#7088](https://github.com/wandb/weave/pull/7088))
  - Add `gen_ai.conversation.id` as attribute on all spans ([#7339](https://github.com/wandb/weave/pull/7339))
  - Add `gen_ai.agent.name` as attribute on all spans ([#7340](https://github.com/wandb/weave/pull/7340))
  - Include integration OTel attrs ([#7341](https://github.com/wandb/weave/pull/7341))
- Updated `GenAI` / `Session` APIs
  - Add `attributes` option to `weave.startSession` ([#7396](https://github.com/wandb/weave/pull/7396))
  - Support passing `endTime` to `weave.endTurn` and `weave.endLLM` ([#7381](https://github.com/wandb/weave/pull/7381))
  - Accept `endTime` on `endSession` and `Session.end` ([#7385](https://github.com/wandb/weave/pull/7385))
  - add `setAttributes`/`addEvent` to `Tool`/`LLM`/`SubAgent`/`Turn` via shared base ([#7195](https://github.com/wandb/weave/pull/7195))
  - post-hoc start/end times on GenAI spans ([#7078](https://github.com/wandb/weave/pull/7078))
  - Add `useOTelv2` setting to `weave.init()` ([#7218](https://github.com/wandb/weave/pull/7218))
- Agent observability read APIs on `WeaveClient`.
  - `getAgents` ([#7232](https://github.com/wandb/weave/pull/7232))
  - `getAgentVersions` ([#7261](https://github.com/wandb/weave/pull/7261))
  - `getAgentSpans` ([#7287](https://github.com/wandb/weave/pull/7287), [#7419](https://github.com/wandb/weave/pull/7419))
  - `getAgentTurn` ([#7288](https://github.com/wandb/weave/pull/7288))
  - `getAgentTurns` ([#7290](https://github.com/wandb/weave/pull/7290))
  - `getAgentSpanStats` ([#7417](https://github.com/wandb/weave/pull/7417))
  - `getAgentCustomAttrsSchema` ([#7418](https://github.com/wandb/weave/pull/7418))
  - `searchAgents` ([#7416](https://github.com/wandb/weave/pull/7416))
- Add `weave.integration` metadata on integrations ([#7103](https://github.com/wandb/weave/pull/7103))
- send `trace_id` on call-end ingest messages ([#7257](https://github.com/wandb/weave/pull/7257))
- send `is_eval` on call-end ingest messages ([#7392](https://github.com/wandb/weave/pull/7392))
- send `x-client-capability` header on ingest (Node) ([#7351](https://github.com/wandb/weave/pull/7351))
- tag declarative evaluation child calls with eval metadata ([#7286](https://github.com/wandb/weave/pull/7286))

### Changed

- **BREAKING:** Remove export of `WeaveClient` value, only export as type. ([#7208](https://github.com/wandb/weave/pull/7208)).
- **BREAKING:** Consolidate settings, expose reference in `docs/`. ([#7217](https://github.com/wandb/weave/pull/7217))

### Fixed

- Respect `startTime` given to `Session.startTurn`. ([#7378](https://github.com/wandb/weave/pull/7378))

[0.16.0]: https://github.com/wandb/weave/releases/tag/weave-ts-v0.16.0
