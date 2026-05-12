import pytest

from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import InvalidRequest
from weave.trace_server.sqlite_trace_server import SqliteTraceServer


def test_sqlite_sampling_rules_update_read_filter_and_delete():
    server = SqliteTraceServer(":memory:")
    server.drop_tables()
    server.setup_tables()
    project_id = "entity/project"

    empty = server.sampling_rules_read(
        tsi.SamplingRulesReadReq(project_id=project_id, consumer="sdk")
    )
    assert empty.rules == []
    assert empty.default_rate == 1.0
    assert empty.schema_version == 1

    project_snapshot = server.sampling_rules_update(
        tsi.SamplingRulesUpdateReq(
            project_id=project_id,
            scope=f"project:{project_id}",
            op_pattern="",
            rate=0.25,
            wb_user_id="user-1",
        )
    )
    assert [(rule.scope, rule.op_pattern, rule.rate) for rule in project_snapshot.rules] == [
        (f"project:{project_id}", "", 0.25)
    ]

    server.sampling_rules_update(
        tsi.SamplingRulesUpdateReq(
            project_id=project_id,
            scope="monitor:mon-1",
            op_pattern="openai.*",
            rate=0.5,
            wb_user_id="monitor:mon-1",
        )
    )

    # SDK consumers never see monitor rules; monitor workers see only their own monitor.
    sdk_snapshot = server.sampling_rules_read(
        tsi.SamplingRulesReadReq(project_id=project_id, consumer="sdk")
    )
    monitor_1_snapshot = server.sampling_rules_read(
        tsi.SamplingRulesReadReq(
            project_id=project_id, consumer="monitor", monitor_id="mon-1"
        )
    )
    monitor_2_snapshot = server.sampling_rules_read(
        tsi.SamplingRulesReadReq(
            project_id=project_id, consumer="monitor", monitor_id="mon-2"
        )
    )
    assert [rule.scope for rule in sdk_snapshot.rules] == [f"project:{project_id}"]
    assert [rule.scope for rule in monitor_1_snapshot.rules] == [
        "monitor:mon-1",
        f"project:{project_id}",
    ]
    assert [rule.scope for rule in monitor_2_snapshot.rules] == [
        f"project:{project_id}"
    ]

    server.sampling_rules_update(
        tsi.SamplingRulesUpdateReq(
            project_id=project_id,
            scope="monitor:mon-1",
            op_pattern="openai.*",
            rate=0.5,
            enabled=False,
            wb_user_id="monitor:mon-1",
        )
    )
    deleted_snapshot = server.sampling_rules_read(
        tsi.SamplingRulesReadReq(
            project_id=project_id, consumer="monitor", monitor_id="mon-1"
        )
    )
    assert [rule.scope for rule in deleted_snapshot.rules] == [f"project:{project_id}"]


def test_sampling_rule_validation_rejects_bad_writes():
    server = SqliteTraceServer(":memory:")
    server.drop_tables()
    server.setup_tables()
    project_id = "entity/project"

    with pytest.raises(InvalidRequest, match="rate must be between 0 and 1"):
        server.sampling_rules_update(
            tsi.SamplingRulesUpdateReq(
                project_id=project_id,
                scope=f"project:{project_id}",
                op_pattern="openai.*",
                rate=1.1,
                wb_user_id="user-1",
            )
        )

    with pytest.raises(InvalidRequest, match="wb_user_id is required"):
        server.sampling_rules_update(
            tsi.SamplingRulesUpdateReq(
                project_id=project_id,
                scope=f"project:{project_id}",
                op_pattern="openai.*",
                rate=0.5,
            )
        )

    with pytest.raises(InvalidRequest, match="no-op"):
        server.sampling_rules_update(
            tsi.SamplingRulesUpdateReq(
                project_id=project_id,
                scope=f"project:{project_id}",
                op_pattern="",
                rate=1.0,
                wb_user_id="user-1",
            )
        )
