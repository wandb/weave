# Weave Remote Scorer Sample

This sample shows the contract for an externally hosted Weave remote scorer. It
is deployment agnostic: the Python service is a reference implementation, not a
hosting recommendation.

In production, deploy an equivalent `POST /score` endpoint behind your normal
HTTPS ingress, API gateway, or service platform. `127.0.0.1`, insecure HTTP, and
tunnels are local-development conveniences only.

## Prerequisites

Remote scoring is coming soon and is not yet generally available. Ask your W&B
representative for more information about availability.

Before using this sample, deploy the scorer endpoint at a public HTTPS URL and
store its OAuth client secret or static bearer token in the W&B secret store for
the entity that owns the project. The secret name, rather than the raw secret,
is used when registering the scorer.

### Multi-Tenant Cloud

Enable Remote Scoring for the organization. An organization admin should open
the organization settings page:

```text
https://wandb.ai/account-settings/YOUR_ORG_HERE/settings
```

Replace `YOUR_ORG_HERE` with the W&B organization that owns your project.
Navigate to **Remote scoring**, enable remote scoring, and configure **Allowed
hosts**.

### Dedicated Cloud and Self-Managed

Ask your deployment administrator to enable remote scoring and configure its
allowed hosts.

### Configuring Allowed Hosts

The scorer endpoint and OAuth token endpoint are validated independently. If
they use different hosts, allow both. Entries match an exact host and may
optionally specify a port; wildcards are not supported. Leaving the port blank
permits any port for that host. Loopback, private, internal, and cloud metadata
addresses are rejected.

## Files

- `remote_scorer_app.py`: minimal FastAPI adapter with `GET /health` and
  `POST /score`.
- `scoring_logic.py`: framework-independent scoring logic that can be copied
  into another web framework or language.
- `auth.py`: dev-only bearer-token validator stub.
- `register_remote_scorer.py`: publishes a `RemoteScorer` and activates a
  `Monitor` for a traced op or for agent turns.
- `trigger_test_trace.py`: sends a small traced call that can trigger an op
  monitor.
- `trigger_test_agent_turn.py`: logs one agent turn that can trigger an
  agent-turn monitor.
- `sample_request.json`: V1 request body for a traced call.
- `sample_request_v2_call.json`: V2 request body for a traced call.
- `sample_request_v2_agent_turn.json`: V2 request body for an agent turn.
- `requirements.txt`: packages needed to run the endpoint, register the scorer,
  and trigger a test trace.

## Remote Scorer Contract

Weave sends an HTTP `POST` to your configured scorer endpoint each time a
monitor selects something to score. A `RemoteScorer` can be attached to two
kinds of monitor:

| Monitor target | How to configure | Request version Weave sends |
| --- | --- | --- |
| A traced op (a call) | `op_names=["my_op"]` | `schema_version: 1` |
| Completed agent turns | `op_names=["weave.genai.turn_ended"]` | `schema_version: 2` |

The two versions share one envelope. They differ only in where the scored
data lives, so one endpoint can accept both. See
[Request versions](#request-versions).

### Headers

Request headers include:

- `Content-Type: application/json`
- `Authorization: Bearer <token>`
- `Idempotency-Key: <stable key for this scoring attempt>`
- `X-Correlation-ID: <request correlation id>`
- `X-Weave-Schema-Version: <1 or 2>`, matching `schema_version` in the body

`Idempotency-Key` is derived from the scored target, the monitor version, and
the scorer version. Weave may deliver the same scoring attempt more than once.
If the scorer performs side effects or writes to a downstream system, use
`Idempotency-Key` to deduplicate repeated attempts. The key is stable for one
request version; a V1 and a V2 request for the same call carry different keys.

### Request versions

Every request carries these top-level fields:

- `schema_version`: integer, currently `1` or `2`.
- `scoring_call_id` and `scoring_trace_id`: identifiers for this scoring
  attempt.
- `monitor`: `name` and `version_digest` of the monitor that selected the
  target.
- `scorer`: `name`, `ref`, and optional `config`. `config` is the mapping you
  set on the `RemoteScorer`, passed through unchanged.
- `triggered_at`: optional ISO 8601 timestamp.

**V1** puts the scored call at the top level under `original_call`. See
`sample_request.json`. Call monitors send V1 today.

**V2** puts the scored data under `scoring_target`, a tagged union with three
fields:

- `type`: the kind of thing being scored, `"call"` or `"agent_turn"`.
- `schema_version`: the version of the payload for that type, independent of
  the top-level envelope version.
- `payload`: the data for that type.

Dispatch on the top-level `schema_version` first, then on the pair
`(scoring_target.type, scoring_target.schema_version)`. Return a 4xx response
for a pair you do not implement. The sample returns `400` with
`unsupported_scoring_target_type` in the body.

The `("call", 1)` payload is the same object V1 sends as `original_call`.
Compare `sample_request.json` with `sample_request_v2_call.json`: only the
wrapper differs. Because of that, one endpoint can accept both by unwrapping
the envelope first and scoring the payload second, as `extract_scoring_target`
in `scoring_logic.py` does. Call monitors send V1 today.

The `("agent_turn", 1)` payload describes one completed agent turn.
`sample_request_v2_agent_turn.json` shows every field. Additional detail:

- Eight fields are `null` when the trace did not record them:
  `operation_name`, the three under `agent`, the two under `conversation`,
  and `status.message` and `status.error_type`. Every other field always has
  a value. The `messages` lists are `[]` when the trace has no messages of
  that kind.
- `status.code` is `"UNSET"`, `"OK"`, or `"ERROR"`. A turn that ends without
  an explicit status arrives as `"UNSET"`, so treat `"UNSET"` as a normal
  completed turn and `"ERROR"` as the failure signal.
- A message `content` is plain text, or a JSON-encoded array of parts when the
  message carried structured content such as tool calls.

Weave may add optional fields to any version without changing its number, so
ignore fields you do not recognize. A field is removed, renamed, or changed in
meaning only with a new `scoring_target.schema_version` for that type, or a
new top-level `schema_version` for envelope changes.

### Request content

Payloads contain JSON text only, never images, audio, or video. Request and
response bodies are each limited to 1 MiB. A target that breaks those rules is
not sent, so it is not scored.

The request carries no W&B credential and no feedback identity. The bearer
token authenticates Weave to your endpoint, not the reverse. Your endpoint
returns a result; Weave records it as feedback on the scored call or turn.

### Response

The endpoint must return HTTP 200 with a JSON object. The required top-level
contract fields are:

- `schema_version`: required integer; must equal the request's
  `schema_version`.
- `result`: required structured scorer output.

`result` takes one of three shapes: one score object, a list of score objects,
or `{"scores": [...]}`. Agent-turn scoring requires this structured form, since
Weave stores the tags and ratings it produces as typed feedback columns.

The simplest structured result is one score object:

- `value`: required; either a tag string, max 36 characters, or a numeric rating
  from `0.0` to `1.0`.
- `reason`: optional string explaining the score.
- `confidence`: optional numeric confidence from `0.0` to `1.0`.

For a single-score response:

```json
{
  "schema_version": 1,
  "result": {
    "value": 1.0,
    "reason": "The response is clear and concise.",
    "confidence": 0.9
  }
}
```

This sample returns one numeric rating and one tag:

```json
{
  "schema_version": 1,
  "result": [
    {
      "value": 1.0,
      "reason": "Message is 32 characters; concise messages score best.",
      "confidence": 1.0
    },
    {
      "value": "concise",
      "reason": "Message length category is concise.",
      "confidence": 0.9
    }
  ]
}
```

The same `result` shape is valid for a V2 request. Only `schema_version`
changes:

```json
{
  "schema_version": 2,
  "result": {"value": "concise", "reason": "72 characters.", "confidence": 0.9}
}
```

### Errors

Weave treats a non-200 response as a scorer failure and records no feedback
for that attempt. Weave does not follow redirects, so a redirect is also a
failure. Retries depend on the request version:

- A V2 agent-turn request that gets a `5xx`, `408`, or `429` response, or
  times out, is sent again with the same `Idempotency-Key`, up to three
  attempts within about 30 seconds.
- A V1 call request is sent once. No response or timeout is retried.

In both versions, any other `4xx` is not retried, so return `4xx` for requests
you will never accept and `5xx` for temporary problems. The response body of
an error is for your logs; Weave does not parse it.

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

From this directory, install the sample dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The minimum supported Weave version is `0.53.0`.

Run the reference endpoint locally:

```bash
export REMOTE_SCORER_DEV_BEARER_TOKEN="dev-token"
uvicorn remote_scorer_app:app --host 127.0.0.1 --port 8000
```

Exercise the local contract without Weave. For a V1 call request:

```bash
curl -sS http://127.0.0.1:8000/score \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: local-contract-check" \
  -H "X-Correlation-ID: local-contract-check" \
  -H "X-Weave-Schema-Version: 1" \
  --data @sample_request.json
```

For a V2 agent-turn request, change the header and the body:

```bash
curl -sS http://127.0.0.1:8000/score \
  -H "Authorization: Bearer dev-token" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: local-contract-check" \
  -H "X-Correlation-ID: local-contract-check" \
  -H "X-Weave-Schema-Version: 2" \
  --data @sample_request_v2_agent_turn.json
```

Substitute `sample_request_v2_call.json` for a V2 call request.

This local check only verifies the endpoint contract. It does not prove that a
Weave deployment can reach a loopback URL.

For production, expose the equivalent endpoint at an HTTPS URL such as:

```text
https://scoring.example.com/weave/score
```

The Weave deployment must be able to reach this host and its configured
allowlist must permit it. See [Configuring Allowed Hosts](#configuring-allowed-hosts).
This sample does not configure TLS itself; in production TLS is usually
terminated by your ingress, API gateway, load balancer, or service mesh.

## Register A Remote Scorer

The register script publishes one `RemoteScorer` and activates one `Monitor`.
By default the monitor targets the traced op `sample_remote_scorer_target`.
Pass `--agent-turn` instead of `--op-name` to target completed agent turns.

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

Agent turns, with static bearer auth:

```bash
python register_remote_scorer.py \
  --project entity/project \
  --score-url https://scoring.example.com/weave/score \
  --agent-turn \
  --monitor-name example_remote_scorer_agent_monitor \
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

Monitor scoring is asynchronous, so feedback will not show up immediately.
Confirm the endpoint received a request and that Weave recorded feedback for
the traced call.

## Trigger A Test Agent Turn

After registering a monitor with `--agent-turn`, run:

```bash
python trigger_test_agent_turn.py \
  --project entity/project \
  --input "What are your support hours?" \
  --output "Our support team is available Monday through Friday, 9am to 5pm Eastern."
```

The script logs one completed turn with `weave.conversation.log_turn`. The
endpoint receives a V2 request with `scoring_target.type` set to
`"agent_turn"`, and Weave records the result as feedback on that turn.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Remote scorer controls are not visible | Confirm remote scoring is enabled in the owning organization's **Remote scoring** settings. |
| Destination is rejected | Confirm both the scorer host and, for OAuth, the token host are in **Allowed hosts**. Check for a port mismatch, a non-HTTPS URL, or a private/internal address. |
| Remote scorer endpoint returns `401` or `403` | Check the W&B secret name, OAuth client credentials, audience, scope, and the scorer endpoint's bearer-token validation. |
| OAuth succeeds but scoring fails, or the reverse | Check each URL separately. The token endpoint and scorer endpoint are independently validated and may use different hosts. Both must be in the allow list. |
| Feedback does not appear immediately | Monitor scoring is asynchronous, so feedback will not show up immediately. Confirm the trace matched the configured operation and sampling rate. |
| Endpoint returns `400` for agent turns | Confirm the endpoint dispatches on the top-level `schema_version` and accepts `scoring_target.type` `"agent_turn"` with inner `schema_version` `1`. |
| Feedback is missing after a `200` response | Confirm `schema_version` in the response equals the request's, and that `result` uses one of the three structured shapes. |

## Adapting This Sample

Most teams should copy the scoring contract, auth validation, and
`score_remote_request` dispatch into an existing approved web service rather
than adopting this exact FastAPI app. The important production requirements
are:

- HTTPS endpoint reachable from Weave.
- Host allowlist configured if the Weave deployment requires it.
- Bearer-token validation implemented with your identity/security standards.
- Dispatch on `schema_version`, then on `scoring_target.type` and its
  `schema_version`, with a `4xx` for targets you do not support.
- HTTP 200 response body shaped as
  `{"schema_version": <request version>, "result": {"value": 0.9, "reason": "...", "confidence": 1.0}}`.
- Unknown request fields ignored.
- Optional dedupe uses `Idempotency-Key`.
