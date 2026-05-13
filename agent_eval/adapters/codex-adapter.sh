#!/bin/bash
# Codex adapter script for agent_eval
#
# Environment variables:
#   AGENT_EVAL_PROMPT      - The user prompt to execute
#   AGENT_EVAL_SKILL_PATH  - Path to skill directory (copied to .codex/skills/)
#   AGENT_EVAL_WORKDIR     - Working directory
#   AGENT_EVAL_TIMEOUT     - Timeout in seconds (handled by Docker, not codex)
#   OPENAI_API_KEY         - OpenAI API key
#
# Codex CLI loads skills from .codex/skills/ in the working directory.
# The Dockerfile copies skills there during image build.

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
WORKDIR="${AGENT_EVAL_WORKDIR:-/workspace}"

# Change to working directory
cd "$WORKDIR"

# Ensure artifacts directories exist
mkdir -p /artifacts/workspace

# Execute codex and capture output
echo "Running codex exec..." >&2
codex exec --json --full-auto "$AGENT_EVAL_PROMPT" > /artifacts/trajectory.jsonl 2>&1 || {
    EXIT_CODE=$?
    echo "Codex exited with code $EXIT_CODE" >&2
    # Still copy the trajectory even on failure
}

# Copy workspace to artifacts
cp -r "$WORKDIR"/* /artifacts/workspace/ 2>/dev/null || true

echo "Execution complete" >&2
