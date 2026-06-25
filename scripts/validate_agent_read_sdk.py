"""Live validation of the WeaveClient agent read SDK against a running trace server.

Drives all eight agent read methods over real HTTP, useful for smoke-testing the
SDK against a local Tilt deploy (or any reachable trace server) end to end:
WeaveClient -> RemoteHTTPTraceServer -> HTTP -> trace server -> ClickHouse.

Usage (run inside the project venv so `weave` is importable):

    export WANDB_API_KEY=...                       # required; read only from env
    export WF_TRACE_SERVER_URL=https://trace...    # or pass --base-url
    # If the server uses a cert your Python trust store doesn't have (e.g. a
    # local *.test Tilt cert), also: export WEAVE_INSECURE_DISABLE_SSL=true
    uv run python scripts/validate_agent_read_sdk.py --entity ENT --project PROJ

The API key is read only from $WANDB_API_KEY and is never written anywhere.
"""

from __future__ import annotations

import argparse
import datetime
import os

from weave.trace.weave_client import WeaveClient
from weave.trace_server.agents import types as agent_types
from weave.trace_server_bindings.remote_http_trace_server import RemoteHTTPTraceServer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("WF_TRACE_SERVER_URL"),
        help="Trace server URL (defaults to $WF_TRACE_SERVER_URL).",
    )
    args = parser.parse_args()
    if not args.base_url:
        parser.error("pass --base-url or set $WF_TRACE_SERVER_URL")

    server = RemoteHTTPTraceServer(
        args.base_url, should_batch=False, auth=("api", os.environ["WANDB_API_KEY"])
    )
    client = WeaveClient(args.entity, args.project, server, ensure_project_exists=False)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    print(f"Target: {args.base_url}   project={client.project_id}\n")

    spans = client.get_agent_spans(limit=5)
    print(f"[get_agent_spans]               total_count={spans.total_count}")

    agents = client.get_agents(limit=10)
    print(f"[get_agents]                    total_count={agents.total_count}")
    for agent in agents.agents[:5]:
        print(
            f"    - {agent.agent_name!r}: span_count={agent.span_count}"
            f" invocations={agent.invocation_count}"
        )

    first_agent = agents.agents[0].agent_name if agents.agents else None
    if first_agent is not None:
        versions = client.get_agent_versions(agent_name=first_agent, limit=5)
        print(
            f"[get_agent_versions {first_agent!r}]"
            f" versions={[v.agent_version for v in versions.versions]}"
        )
        filtered = client.get_agent_spans(agent_name=first_agent, limit=5)
        all_match = all(s.agent_name == first_agent for s in filtered.spans)
        print(
            f"[get_agent_spans agent_name]    total_count={filtered.total_count}"
            f" all_match={all_match}"
        )

    if spans.spans:
        first = spans.spans[0].model_dump()
        turn = client.get_agent_turn(trace_id=first["trace_id"])
        print(
            f"[get_agent_turn]                root={turn.root_span_name!r}"
            f" messages={len(turn.messages)}"
        )
        if first.get("conversation_id"):
            turns = client.get_agent_turns(conversation_id=first["conversation_id"])
            print(f"[get_agent_turns]               total_turns={turns.total_turns}")

    stats = client.get_agent_span_stats(
        start=now - datetime.timedelta(days=30),
        end=now + datetime.timedelta(days=1),
        metrics=[
            agent_types.AgentSpanStatsMetricSpec(
                alias="input_tokens",
                value_type="number",
                value=agent_types.AgentSpanValueRef(
                    source="field", key="usage.input_tokens"
                ),
                aggregations=["sum"],
            )
        ],
    )
    print(
        f"[get_agent_span_stats]          columns={[c.name for c in stats.columns]}"
        f" rows={len(stats.rows)}"
    )

    schema = client.get_agent_custom_attrs_schema()
    print(f"[get_agent_custom_attrs_schema] attributes={len(schema.attributes)}")

    search = client.search_agents(query="")
    print(
        f"[search_agents]                 results={len(search.results)}"
        f" total_conversations={search.total_conversations}"
    )

    print("\nAll 8 agent read SDK methods executed over real HTTP.")


if __name__ == "__main__":
    main()
