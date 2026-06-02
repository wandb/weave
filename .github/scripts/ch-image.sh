#!/usr/bin/env bash
# Resolve a ClickHouse image via GHCR to dodge Docker Hub pull rate limits in CI.
# Mirrors clickhouse/clickhouse-server:<tag> into GHCR on first use, then prints
# the runnable image ref on stdout (everything else goes to stderr).
set -uo pipefail

# Single source of truth for the ClickHouse image version used across CI.
tag="${1:-25.11.2.24}"
ghcr="ghcr.io/wandb/clickhouse-server:${tag}"
hub="clickhouse/clickhouse-server:${tag}"

if [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${GITHUB_ACTOR:-wandb}" --password-stdin 1>&2 || true
fi

if docker pull "$ghcr" 1>&2 2>/dev/null; then
  echo "$ghcr"
  exit 0
fi

echo "Mirroring ${hub} -> ${ghcr}" 1>&2
docker pull "$hub" 1>&2
docker tag "$hub" "$ghcr"
if docker push "$ghcr" 1>&2; then
  echo "$ghcr"
else
  echo "GHCR push skipped (no write access); running from Docker Hub image" 1>&2
  echo "$hub"
fi
