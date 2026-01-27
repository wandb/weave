"""Tests for the trace_usage endpoint."""
from datetime import datetime, timezone

import pytest
import uuid
from tests.trace_server.conftest import TEST_ENTITY
from weave.trace_server import trace_server_interface as tsi
class TestTraceUsage:
    """Tests for /trace/usage endpoint (per-call usage with descendant rollup)."""

    def test_single_call(self, trace_server):
        """Test trace usage with a single root call."""
        server = trace_server
        project_id = f"{TEST_ENTITY}/trace_usage_single_call"
        trace_id = str(uuid.uuid4())

        # Create a call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="call1",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id=None,
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="call1",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {
                                "prompt_tokens": 100,
                                "completion_tokens": 50,
                                "requests": 1,
                            }
                        }
                    },
                )
            )
        )

        res = server.trace_usage(
            tsi.TraceUsageReq(
                project_id=project_id,
                filter=tsi.CallsFilter(trace_ids=[trace_id]),
            )
        )

        assert "call1" in res.call_usage
        usage = res.call_usage["call1"]
        assert usage["gpt-4"].prompt_tokens == 100
        assert usage["gpt-4"].completion_tokens == 50

    def test_parent_child_rollup(self, trace_server):
        """Test that child metrics roll up to parent."""
        server = trace_server
        project_id = f"{TEST_ENTITY}/trace_usage_parent_child_rollup"
        trace_id = str(uuid.uuid4())

        # Create root call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="root",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id=None,
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="root",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {
                                "prompt_tokens": 100,
                                "completion_tokens": 50,
                            }
                        }
                    },
                )
            )
        )

        # Create child call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="child",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id="root",
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="child",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {
                                "prompt_tokens": 200,
                                "completion_tokens": 100,
                            }
                        }
                    },
                )
            )
        )

        res = server.trace_usage(
            tsi.TraceUsageReq(
                project_id=project_id,
                filter=tsi.CallsFilter(trace_ids=[trace_id]),
            )
        )

        # Child should have only its own metrics
        child_usage = res.call_usage["child"]
        assert child_usage["gpt-4"].prompt_tokens == 200
        assert child_usage["gpt-4"].completion_tokens == 100

        # Root should have its own + child's metrics
        root_usage = res.call_usage["root"]
        assert root_usage["gpt-4"].prompt_tokens == 300  # 100 + 200
        assert root_usage["gpt-4"].completion_tokens == 150  # 50 + 100

    def test_deep_hierarchy(self, trace_server):
        """Test recursive aggregation with a deeper call hierarchy."""
        server = trace_server
        project_id = f"{TEST_ENTITY}/trace_usage_deep_hierarchy"
        trace_id = str(uuid.uuid4())

        # Tree structure:
        # root (100 tokens)
        #   ├─ child1 (200 tokens)
        #   │    └─ grandchild1 (300 tokens)
        #   └─ child2 (400 tokens)

        calls_data = [
            ("root", None, 100),
            ("child1", "root", 200),
            ("grandchild1", "child1", 300),
            ("child2", "root", 400),
        ]

        for call_id, parent_id, tokens in calls_data:
            server.call_start(
                tsi.CallStartReq(
                    start=tsi.StartedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id,
                        op_name="test_op",
                        trace_id=trace_id,
                        parent_id=parent_id,
                        started_at=datetime.now(timezone.utc),
                        attributes={},
                        inputs={},
                    )
                )
            )
            server.call_end(
                tsi.CallEndReq(
                    end=tsi.EndedCallSchemaForInsert(
                        project_id=project_id,
                        id=call_id,
                        ended_at=datetime.now(timezone.utc),
                        summary={
                            "usage": {
                                "gpt-4": {"prompt_tokens": tokens},
                            }
                        },
                    )
                )
            )

        res = server.trace_usage(
            tsi.TraceUsageReq(
                project_id=project_id,
                filter=tsi.CallsFilter(trace_ids=[trace_id]),
            )
        )

        # grandchild1 has only its own
        assert res.call_usage["grandchild1"]["gpt-4"].prompt_tokens == 300

        # child1 has its own + grandchild1
        assert res.call_usage["child1"]["gpt-4"].prompt_tokens == 500  # 200 + 300

        # child2 has only its own
        assert res.call_usage["child2"]["gpt-4"].prompt_tokens == 400

        # root has its own + child1 (with grandchild) + child2
        assert res.call_usage["root"]["gpt-4"].prompt_tokens == 1000  # 100 + 500 + 400

    def test_mixed_llms_in_hierarchy(self, trace_server):
        """Test recursive aggregation with different LLMs at different levels."""
        server = trace_server
        project_id = f"{TEST_ENTITY}/trace_usage_mixed_llms"
        trace_id = str(uuid.uuid4())

        # Root uses gpt-4
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="root",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id=None,
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="root",
                    ended_at=datetime.now(timezone.utc),
                    summary={"usage": {"gpt-4": {"prompt_tokens": 100}}},
                )
            )
        )

        # Child uses claude-3
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="child",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id="root",
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="child",
                    ended_at=datetime.now(timezone.utc),
                    summary={"usage": {"claude-3": {"prompt_tokens": 200}}},
                )
            )
        )

        res = server.trace_usage(
            tsi.TraceUsageReq(
                project_id=project_id,
                filter=tsi.CallsFilter(trace_ids=[trace_id]),
            )
        )

        # Child has only claude-3
        assert "claude-3" in res.call_usage["child"]
        assert "gpt-4" not in res.call_usage["child"]

        # Root has both gpt-4 (its own) and claude-3 (from child)
        root_usage = res.call_usage["root"]
        assert root_usage["gpt-4"].prompt_tokens == 100
        assert root_usage["claude-3"].prompt_tokens == 200


class TestTraceUsageIntegration:
    """Integration tests using actual database operations."""

    def test_full_workflow_trace_usage(self, trace_server):
        """Test full workflow with trace_usage (per-call with rollup)."""
        server = trace_server
        project_id = f"{TEST_ENTITY}/trace_usage_full_workflow"
        trace_id = str(uuid.uuid4())

        # Create root call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="root",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id=None,
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="root",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {"prompt_tokens": 100},
                        }
                    },
                )
            )
        )

        # Create child call
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="child",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id="root",
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="child",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {"prompt_tokens": 200},
                        }
                    },
                )
            )
        )

        # Test trace_usage
        res = server.trace_usage(
            tsi.TraceUsageReq(
                project_id=project_id,
                filter=tsi.CallsFilter(trace_ids=[trace_id]),
            )
        )

        assert "root" in res.call_usage
        assert "child" in res.call_usage

        # Root should have aggregated metrics (own + child)
        assert res.call_usage["root"]["gpt-4"].prompt_tokens == 300

        # Child should have only its own metrics
        assert res.call_usage["child"]["gpt-4"].prompt_tokens == 200

    def test_with_costs(self, trace_server):
        """Test trace_usage with cost data."""
        server = trace_server
        project_id = f"{TEST_ENTITY}/trace_usage_with_costs"
        trace_id = str(uuid.uuid4())

        # Complete cost data matching LLMCostSchema requirements
        cost_data = {
            "prompt_tokens_total_cost": 0.003,
            "completion_tokens_total_cost": 0.002,
            "prompt_token_cost": 0.00003,
            "completion_token_cost": 0.00004,
            "prompt_token_cost_unit": "USD",
            "completion_token_cost_unit": "USD",
            "effective_date": "2024-01-01",
            "provider_id": "openai",
            "pricing_level": "default",
            "pricing_level_id": "default",
            "created_at": "2024-01-01T00:00:00Z",
            "created_by": "test",
        }

        # Create call with costs
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="call1",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id=None,
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="call1",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {
                                "prompt_tokens": 100,
                                "completion_tokens": 50,
                            }
                        },
                        "weave": {"costs": {"gpt-4": cost_data}},
                    },
                )
            )
        )

        # Create another call with costs
        server.call_start(
            tsi.CallStartReq(
                start=tsi.StartedCallSchemaForInsert(
                    project_id=project_id,
                    id="call2",
                    op_name="test_op",
                    trace_id=trace_id,
                    parent_id="call1",
                    started_at=datetime.now(timezone.utc),
                    attributes={},
                    inputs={},
                )
            )
        )
        server.call_end(
            tsi.CallEndReq(
                end=tsi.EndedCallSchemaForInsert(
                    project_id=project_id,
                    id="call2",
                    ended_at=datetime.now(timezone.utc),
                    summary={
                        "usage": {
                            "gpt-4": {
                                "prompt_tokens": 100,
                                "completion_tokens": 50,
                            }
                        },
                        "weave": {"costs": {"gpt-4": cost_data}},
                    },
                )
            )
        )

        # Test trace_usage with include_costs=True
        res = server.trace_usage(
            tsi.TraceUsageReq(
                project_id=project_id,
                filter=tsi.CallsFilter(trace_ids=[trace_id]),
                include_costs=True,
            )
        )

        # Root should have sum of costs
        root_usage = res.call_usage["call1"]
        assert root_usage["gpt-4"].prompt_tokens_total_cost == pytest.approx(0.006)
