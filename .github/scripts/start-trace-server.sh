#!/usr/bin/env bash
# Start TRACE_SERVER_COUNT copies of core's resettable trace server from core's
# source, each on its own ClickHouse database, for the weave tests.
#
# Expects wandb/core at $CORE_DIR with this weave commit checked out at
# $CORE_DIR/services/weave-trace/weave-public, COMPOSE_FILE set to core's
# compose file, uv on PATH and Docker logged in to Artifact Registry. Servers
# listen on 127.0.0.1:6345 and up and log to $RUNNER_TEMP/trace-server. Writes
# WANDB_API_KEY, WF_TRACE_SERVER_URL (the first server) and
# WEAVE_TEST_TRACE_SERVER_URLS (all of them) to $GITHUB_ENV.
set -euo pipefail

count="${TRACE_SERVER_COUNT:-1}"
logs="${RUNNER_TEMP}/trace-server"
mkdir -p "${logs}"

wait_for() {  # description, attempts, command...
  local what=$1 attempts=$2
  shift 2
  for _i in $(seq "${attempts}"); do
    "$@" >/dev/null 2>&1 && return 0
    sleep 2
  done
  echo "::error::${what} did not become ready in time"
  return 1
}

gorilla_ready() {
  (curl --silent --fail http://localhost:8080/ready || curl --silent --fail http://localhost:8080/healthz) \
    && curl --silent --fail http://localhost:9015/health
}

cd "${CORE_DIR}"

# Gorilla is the largest image and the slowest to boot, so it goes first.
(docker compose pull --quiet wandb-local && docker compose up --detach wandb-local) &
gorilla=$!
# The server runs from core's source, so only its Python deps are installed.
(cd services/weave-trace && uv sync --frozen --no-install-project --no-dev) &
deps=$!
# Serve core's ClickHouse image from the GHCR mirror to avoid Docker Hub limits.
ch_tag="$(sed -n 's|.*image: clickhouse/clickhouse-server:||p' "${COMPOSE_FILE}")"
ch_image="$("${GITHUB_WORKSPACE}/.github/scripts/ch-image.sh" "${ch_tag}")"
docker tag "${ch_image}" "clickhouse/clickhouse-server:${ch_tag}"
docker compose up --detach clickhouse

wait_for ClickHouse 60 curl --silent --fail http://localhost:8123/ping
wait "${deps}"
cd services/weave-trace
migrations=()
for i in $(seq 0 $((count - 1))); do
  .venv/bin/python -m src.migrator localhost 8123 default "" "weave_${i}" \
    > "${logs}/migrate-${i}.log" 2>&1 &
  migrations+=($!)
done
for pid in "${migrations[@]}"; do wait "${pid}"; done

urls=()
for i in $(seq 0 $((count - 1))); do
  port=$((6345 + i))
  urls+=("http://127.0.0.1:${port}")
  WF_CLICKHOUSE_DATABASE="weave_${i}" \
    WANDB_BASE_URL=http://localhost:8080 \
    WEAVE_TRACE_CLICKHOUSE_USE_ASYNC_INSERT=false \
    DISABLE_TELEMETRY=true \
    DD_TRACE_ENABLED=false \
    nohup .venv/bin/uvicorn src.tests.support.resettable_trace_server:app \
      --host 127.0.0.1 --port "${port}" --reset-contextvars \
      > "${logs}/server-${i}.log" 2>&1 &
done

wait "${gorilla}"
wait_for Gorilla 120 gorilla_ready
# The tests log to TEST_ENTITY (tests/trace/server_utils.py).
api_key="shawn-$(openssl rand -hex 20)"
echo "::add-mask::${api_key}"
curl --silent --fail --show-error http://localhost:9015/db/user \
  --header "Content-Type: application/json" \
  --data "{\"command\": \"up\", \"username\": \"shawn\", \"apiKey\": \"${api_key}\"}"
# Every test process writes to the client fixture's project (tests/conftest.py),
# and when several create a project at once, Gorilla fails all but one.
curl --silent --fail --show-error --user "api:${api_key}" http://localhost:8080/graphql \
  --header "Content-Type: application/json" \
  --data '{"query": "mutation { upsertModel(input: {entityName: \"shawn\", name: \"test-project\"}) { project { id } } }"}'

for url in "${urls[@]}"; do
  wait_for "Trace server ${url}" 60 curl --silent --fail "${url}/health"
done

{
  echo "WANDB_API_KEY=${api_key}"
  echo "WF_TRACE_SERVER_URL=${urls[0]}"
  echo "WEAVE_TEST_TRACE_SERVER_URLS=$(IFS=,; echo "${urls[*]}")"
} >> "${GITHUB_ENV}"
