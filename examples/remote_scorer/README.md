# Weave Remote Scorer Sample

This sample shows the contract for an externally hosted Weave remote scorer. It
is deployment agnostic: the Python service is a reference implementation, not a
hosting recommendation.

In production, deploy an equivalent `POST /score` endpoint behind your normal
HTTPS ingress, API gateway, or service platform. `127.0.0.1`, insecure HTTP, and
tunnels are local-development conveniences only.

## Files

- `remote_scorer_app.py`: minimal FastAPI adapter with `GET /health` and
  `POST /score`.
- `scoring_logic.py`: framework-independent scoring logic that can be copied
  into another web framework or language.
- `auth.py`: bearer-token extraction and a dev-only validator stub.
- `register_remote_scorer.py`: publishes a `RemoteScorer` and activates a
  `Monitor`.
- `trigger_test_trace.py`: sends a small traced call that can trigger the
  monitor.
- `sample_request.json`: representative request body sent by Weave.
- `requirements.txt`: packages needed to run the reference endpoint.

## Remote Scorer Contract

Weave sends an HTTP `POST` to your configured scorer endpoint.

Request headers include:

- `Authorization: Bearer <token>`
- `Idempotency-Key: <stable key for this scoring attempt>`
- `X-Correlation-ID: <request correlation id>`
- `X-Weave-Schema-Version: 1`

If the scorer performs side effects or writes to a downstream system, it may use
`Idempotency-Key` to deduplicate retries or repeated scoring attempts.

The endpoint must return HTTP 200 with a JSON object. The required top-level
contract fields are:

- `schema_version`: required integer; must be `1`.
- `result`: required; can be any JSON-serializable shape you choose.

For example:

```json
{
  "schema_version": 1,
  "result": {
    "message_length": 32
  }
}
```

Non-200 responses are treated as scorer failures by Weave. The `result` value is
the scorer output that Weave records as feedback.

## Auth

Use explicit per-scorer auth in production. This sample supports two Weave
registration modes:

- `oauth_client_credentials`: recommended for enterprise deployments. Weave
  fetches a bearer token from your OAuth token endpoint using a client ID and a
  secret stored in the Weave/entity secret store, then sends that token to
  `/score`.
- `static_bearer`: Weave reads a static bearer token from Weave's/entity's
  secret store and sends it to `/score`.

This sample does not include a production OAuth server. Most enterprise
environments already have an identity provider or token service. Replace
`validate_bearer_token` in `auth.py` with one of:

- JWT validation against your JWKS, issuer, audience, expiry, and scope.
- Token introspection against your identity provider for opaque tokens.

The included validator checks `REMOTE_SCORER_DEV_BEARER_TOKEN` and is for local
development only.

Raw OAuth client secrets and bearer tokens should never be committed. Only
secret names are stored in the Weave `RemoteScorer` configuration.

## Local Reference Run

From this directory, install the endpoint dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`requirements.txt` installs only the packages needed to run the reference HTTP
endpoint. To run `register_remote_scorer.py` or `trigger_test_trace.py` from the
repo checkout, also install Weave in editable mode with the scorer extras:

```bash
python -m pip install -e "../..[scorers]"
```

The editable install is needed because these scripts depend on Weave `0.52.43`,
which has not been released yet. The scorer extras are needed by the current
Weave package import path used by the registration script.

Run the reference endpoint locally:

```bash
export REMOTE_SCORER_DEV_BEARER_TOKEN="dev-token"
uvicorn remote_scorer_app:app --host 0.0.0.0 --port 8000
```

Exercise the local contract without Weave:

```bash
curl -sS http://127.0.0.1:8000/score \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: local-contract-check" \
  -H "X-Correlation-ID: local-contract-check" \
  -H "X-Weave-Schema-Version: 1" \
  --data @sample_request.json
```

This local check only verifies the endpoint contract. It does not prove that a
managed Weave deployment can reach a loopback URL.

For production, expose the equivalent endpoint at an HTTPS URL such as:

```text
https://scoring.example.com/weave/score
```

The Weave deployment must be able to reach this host. Depending on the
deployment, the host may need to be added to the remote scorer allowlist. This
sample does not configure TLS itself; in production TLS is usually terminated by
your ingress, API gateway, load balancer, or service mesh.

## Register A Remote Scorer

OAuth client credentials:

```bash
python register_remote_scorer.py \
  --project entity/project \
  --score-url https://scoring.example.com/weave/score \
  --op-name sample_remote_scorer_target \
  --auth-mode oauth_client_credentials \
  --token-url https://idp.example.com/oauth2/token \
  --client-id weave-remote-scorer \
  --secret-name WEAVE_REMOTE_SCORER_CLIENT_SECRET \
  --scope score:remote
```

Static bearer:

```bash
python register_remote_scorer.py \
  --project entity/project \
  --score-url https://scoring.example.com/weave/score \
  --op-name sample_remote_scorer_target \
  --auth-mode static_bearer \
  --secret-name WEAVE_REMOTE_SCORER_BEARER_TOKEN
```

For local-only testing against `http://127.0.0.1:8000/score`, your Weave
deployment must explicitly allow insecure HTTP and loopback/private addresses.
Most hosted or managed deployments will not allow this. Use an HTTPS endpoint
reachable from the Weave scoring worker for realistic testing.

## Trigger A Test Trace

After registering a monitor for `sample_remote_scorer_target`, run:

```bash
python trigger_test_trace.py \
  --project entity/project \
  --op-name sample_remote_scorer_target \
  --message "test message for scoring"
```

Monitor scoring is asynchronous. Confirm the endpoint received a request and
that Weave recorded feedback for the traced call.

## Adapting This Sample

Most teams should copy the scoring contract, auth validation, and
`score_remote_call` behavior into an existing approved web service rather than
adopting this exact FastAPI app. The important production requirements are:

- HTTPS endpoint reachable from Weave.
- Host allowlist configured if the Weave deployment requires it.
- Bearer-token validation implemented with your identity/security standards.
- HTTP 200 response body shaped as `{"schema_version": 1, "result": ...}`.
- Optional dedupe uses `Idempotency-Key`.
