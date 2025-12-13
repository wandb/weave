#!/bin/bash
# Weave Feedback Handler
# Usage: feedback.sh <session_id> <emoji> [note...]
#
# Examples:
#   feedback.sh abc123 "🤩" "Great session!"
#   feedback.sh abc123 "😊"

set -e

# Minimum required weave version
MIN_VERSION="0.52.23"

# Function to compare versions (handles dev versions like 0.52.23.dev0)
version_gte() {
    local version="$1"
    local min="$2"
    local base_version=$(echo "$version" | sed -E 's/[.-](dev|post|rc|a|b)[0-9]*$//')
    local min_of_two=$(printf '%s\n%s' "$base_version" "$min" | sort -V | head -n1)
    [[ "$min_of_two" == "$min" ]]
}

# Function to get weave version from python
get_weave_version() {
    python -c "import weave; print(weave.__version__)" 2>/dev/null
}

# Function to check if weave is installed and meets version requirement
check_weave() {
    if ! command -v python &> /dev/null; then
        return 1
    fi
    local version=$(get_weave_version)
    if [[ -z "$version" ]]; then
        return 1
    fi
    if ! version_gte "$version" "$MIN_VERSION"; then
        return 1
    fi
    return 0
}

# Validate arguments
if [[ $# -lt 2 ]]; then
    echo "Usage: feedback.sh <session_id> <emoji> [note...]" >&2
    exit 1
fi

SESSION_ID="$1"
EMOJI="$2"
shift 2
NOTE="$*"

# Try local python + weave first
if check_weave; then
    if [[ -n "$NOTE" ]]; then
        python -m weave.integrations.claude_plugin.feedback "$SESSION_ID" "$EMOJI" "$NOTE"
    else
        python -m weave.integrations.claude_plugin.feedback "$SESSION_ID" "$EMOJI"
    fi
    exit $?
fi

# Fall back to uvx if available
if command -v uvx &> /dev/null; then
    if [[ -n "$NOTE" ]]; then
        uvx --from "weave>=${MIN_VERSION}" python -m weave.integrations.claude_plugin.feedback "$SESSION_ID" "$EMOJI" "$NOTE"
    else
        uvx --from "weave>=${MIN_VERSION}" python -m weave.integrations.claude_plugin.feedback "$SESSION_ID" "$EMOJI"
    fi
    exit $?
fi

echo "Error: weave not found. Install with 'pip install weave' or 'uv tool install weave'" >&2
exit 1
