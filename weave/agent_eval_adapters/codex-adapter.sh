#!/bin/bash
# Codex adapter script for agent_eval
#
# Environment variables:
#   AGENT_EVAL_PROMPT      - The user prompt to execute
#   AGENT_EVAL_SKILL_PATH  - Path to skill directory
#   AGENT_EVAL_WORKDIR     - Working directory
#   AGENT_EVAL_TIMEOUT     - Timeout in seconds
#   OPENAI_API_KEY         - OpenAI API key

set -e

# Validate required environment variables
if [ -z "$AGENT_EVAL_PROMPT" ]; then
    echo "Error: AGENT_EVAL_PROMPT is required" >&2
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY is required" >&2
    exit 1
fi

# Set defaults
SKILL_PATH="${AGENT_EVAL_SKILL_PATH:-/skill}"
WORKDIR="${AGENT_EVAL_WORKDIR:-/workspace}"
TIMEOUT="${AGENT_EVAL_TIMEOUT:-300}"

# Change to working directory
cd "$WORKDIR"

# Build codex command
CMD="codex exec --json --full-auto"

# Add skills path if it exists
if [ -d "$SKILL_PATH" ]; then
    CMD="$CMD --skills-path $SKILL_PATH"
fi

# Add timeout
CMD="$CMD --timeout $TIMEOUT"

# Execute and capture output
echo "Running: $CMD \"$AGENT_EVAL_PROMPT\"" >&2
$CMD "$AGENT_EVAL_PROMPT" > /artifacts/trajectory.jsonl

# Copy workspace to artifacts
cp -r "$WORKDIR"/* /artifacts/workspace/ 2>/dev/null || true

echo "Execution complete" >&2
