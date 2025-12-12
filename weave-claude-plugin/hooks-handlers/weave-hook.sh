#!/bin/bash
# Weave Claude Plugin Hook Handler
# This script routes Claude Code hooks to the weave.integrations.claude_plugin module.
# It first tries to use the local python/weave installation, then falls back to uvx.

set -e

# Minimum required weave version (major.minor.patch)
MIN_VERSION="0.52.23"

# Function to compare versions (handles dev versions like 0.52.23.dev0)
version_gte() {
    local version="$1"
    local min="$2"

    # Extract base version (strip -devN, .devN, .postN, etc.)
    local base_version=$(echo "$version" | sed -E 's/[.-](dev|post|rc|a|b)[0-9]*$//')

    # Use sort -V for version comparison
    local min_of_two=$(printf '%s\n%s' "$base_version" "$min" | sort -V | head -n1)

    # If min version is the smallest or equal, then version >= min
    [[ "$min_of_two" == "$min" ]]
}

# Function to get weave version from python
get_weave_version() {
    python -c "import weave; print(weave.__version__)" 2>/dev/null
}

# Function to check if weave is installed and meets version requirement
check_weave() {
    # Check if python is available
    if ! command -v python &> /dev/null; then
        return 1
    fi

    # Check if weave is importable
    local version=$(get_weave_version)
    if [[ -z "$version" ]]; then
        return 1
    fi

    # Check version
    if ! version_gte "$version" "$MIN_VERSION"; then
        return 1
    fi

    return 0
}

# Read stdin into a variable (hooks pass payload via stdin)
STDIN_DATA=$(cat)

export WEAVE_PROJECT="${WEAVE_PROJECT:-claude-code-plugin-test}"
# Try local python + weave first
if check_weave; then
    echo "$STDIN_DATA" | python -m weave.integrations.claude_plugin
    exit $?
fi

# Fall back to uvx if available
if command -v uvx &> /dev/null; then
    echo "$STDIN_DATA" | uvx --from "weave>=${MIN_VERSION}" python -m weave.integrations.claude_plugin
    exit $?
fi

# Neither option available - exit silently (don't break Claude Code)
# The hook module itself handles missing WEAVE_PROJECT gracefully
exit 0
