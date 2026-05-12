#!/usr/bin/env bash
set -uo pipefail

max_attempts="${MAX_ATTEMPTS:-3}"
for attempt in $(seq 1 "$max_attempts"); do
  echo "::group::Attempt $attempt of $max_attempts"
  if "$@"; then
    echo "::endgroup::"
    echo "Succeeded on attempt $attempt"
    exit 0
  fi
  echo "::endgroup::"
  echo "Attempt $attempt failed"
done
echo "All $max_attempts attempts failed"
exit 1
