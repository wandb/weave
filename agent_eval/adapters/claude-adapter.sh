#!/bin/bash
# Claude Code adapter script for agent_eval
#
# Environment variables:
#   AGENT_EVAL_PROMPT      - The user prompt to execute
#   AGENT_EVAL_SKILL_PATH  - Path to skill directory
#   AGENT_EVAL_WORKDIR     - Working directory
#   AGENT_EVAL_TIMEOUT     - Timeout in seconds
#   ANTHROPIC_API_KEY      - Anthropic API key

set -e

# Validate required environment variables
if [ -z "$AGENT_EVAL_PROMPT" ]; then
    echo "Error: AGENT_EVAL_PROMPT is required" >&2
    exit 1
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY is required" >&2
    exit 1
fi

# Set defaults
SKILL_PATH="${AGENT_EVAL_SKILL_PATH:-/skill}"
WORKDIR="${AGENT_EVAL_WORKDIR:-/workspace}"
TIMEOUT="${AGENT_EVAL_TIMEOUT:-300}"

# Change to working directory
cd "$WORKDIR"

# Copy skill files to workspace if they exist (Claude reads from cwd)
if [ -d "$SKILL_PATH" ]; then
    mkdir -p .claude/skills
    cp -r "$SKILL_PATH"/* .claude/skills/ 2>/dev/null || true
fi

# Build claude command
CMD="claude --print --output-format json --max-turns 100"

# Execute and capture output
echo "Running: $CMD --prompt \"$AGENT_EVAL_PROMPT\"" >&2
$CMD --prompt "$AGENT_EVAL_PROMPT" > /artifacts/trajectory.jsonl

# Copy workspace to artifacts
cp -r "$WORKDIR"/* /artifacts/workspace/ 2>/dev/null || true

echo "Execution complete" >&2
