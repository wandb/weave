#!/bin/bash
# OpenCode adapter script for agent_eval
#
# Environment variables:
#   AGENT_EVAL_PROMPT      - The user prompt to execute
#   AGENT_EVAL_SKILL_PATH  - Path to skill directory
#   AGENT_EVAL_WORKDIR     - Working directory
#   AGENT_EVAL_TIMEOUT     - Timeout in seconds
#   OPENAI_API_KEY         - OpenAI API key (for OpenAI models)
#   ANTHROPIC_API_KEY      - Anthropic API key (for Claude models)

set -e

# Validate required environment variables
if [ -z "$AGENT_EVAL_PROMPT" ]; then
    echo "Error: AGENT_EVAL_PROMPT is required" >&2
    exit 1
fi

# Set defaults
SKILL_PATH="${AGENT_EVAL_SKILL_PATH:-/skill}"
WORKDIR="${AGENT_EVAL_WORKDIR:-/workspace}"
TIMEOUT="${AGENT_EVAL_TIMEOUT:-300}"

# Change to working directory
cd "$WORKDIR"

# Build opencode command
CMD="opencode exec --json"

# Add skills path if it exists
if [ -d "$SKILL_PATH" ]; then
    CMD="$CMD --skills-path $SKILL_PATH"
fi

# Execute and capture output
echo "Running: $CMD \"$AGENT_EVAL_PROMPT\"" >&2
$CMD "$AGENT_EVAL_PROMPT" > /artifacts/trajectory.jsonl

# Copy workspace to artifacts
cp -r "$WORKDIR"/* /artifacts/workspace/ 2>/dev/null || true

echo "Execution complete" >&2
