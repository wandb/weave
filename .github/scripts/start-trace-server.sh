#!/usr/bin/env bash
# Start core's resettable trace server for the weave client tests, with this
# weave commit mounted over the image's copy of weave.
#
# Expects wandb/core at $CORE_DIR with this weave commit checked out at
# $CORE_DIR/services/weave-trace/weave-public, COMPOSE_FILE set to core's
# compose file, and Docker logged in to Artifact Registry. Writes
# WANDB_API_KEY for the test user to $GITHUB_ENV.
set -euo pipefail

cd "${CORE_DIR}"

# Serve core's ClickHouse image from the GHCR mirror to avoid Docker Hub limits.
ch_tag="$(sed -n 's|.*image: clickhouse/clickhouse-server:||p' "${COMPOSE_FILE}")"
ch_image="$("${GITHUB_WORKSPACE}/.github/scripts/ch-image.sh" "${ch_tag}")"
docker tag "${ch_image}" "clickhouse/clickhouse-server:${ch_tag}"
docker compose up --detach wandb-local clickhouse

image="us-central1-docker.pkg.dev/wandb-production/images/weave-trace:$(git rev-parse HEAD)"
# Core publishes the image a few minutes after each merge to master.
for _i in {1..30}; do
  if docker pull --quiet "${image}"; then
    break
  fi
  if [[ "${_i}" == 30 ]]; then
    echo "::error::${image} was not published in time"
    exit 1
  fi
  sleep 20
done

for _i in {1..60}; do
  curl --silent --fail http://localhost:8123/ping >/dev/null && break
  if [[ "${_i}" == 60 ]]; then
    echo "::error::ClickHouse did not become ready in time"
    exit 1
  fi
  sleep 2
done

for _i in {1..120}; do
  if (curl --silent --fail http://localhost:8080/ready >/dev/null \
      || curl --silent --fail http://localhost:8080/healthz >/dev/null) \
    && curl --silent --fail http://localhost:9015/health >/dev/null; then
    break
  fi
  if [[ "${_i}" == 120 ]]; then
    echo "::error::Gorilla did not become ready in time"
    exit 1
  fi
  sleep 2
done

# The tests log to TEST_ENTITY (tests/trace/server_utils.py).
api_key="shawn-$(openssl rand -hex 20)"
echo "::add-mask::${api_key}"
curl --silent --fail --show-error http://localhost:9015/db/user \
  --header "Content-Type: application/json" \
  --data "{\"command\": \"up\", \"username\": \"shawn\", \"apiKey\": \"${api_key}\"}"
echo "WANDB_API_KEY=${api_key}" >> "${GITHUB_ENV}"

cd services/weave-trace
make copy_weave_code
weave_code="${PWD}/_build/weave_copy:/weave/weave:ro"
docker run --rm --network host --volume "${weave_code}" "${image}" \
  python -m src.migrator localhost 8123 default "" default
docker run --detach --name trace-server --network host --volume "${weave_code}" \
  --env WANDB_BASE_URL=http://localhost:8080 \
  --env WEAVE_TRACE_CLICKHOUSE_USE_ASYNC_INSERT=false \
  --env DISABLE_TELEMETRY=true \
  --env DD_TRACE_ENABLED=false \
  "${image}" \
  uvicorn src.tests.support.resettable_trace_server:app \
    --host 127.0.0.1 --port 6345 --reset-contextvars
for _i in {1..60}; do
  curl --silent --fail http://127.0.0.1:6345/health >/dev/null && exit 0
  sleep 1
done
echo "::error::Trace server did not become ready in time"
exit 1
