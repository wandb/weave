import json

import pytest
from pydantic import BaseModel

from weave.trace_server.datadog import DD_TAG_MAX_LEN, tag_request


class Inner(BaseModel):
    x: int
    y: int


class FakeReq(BaseModel):
    project_id: str
    filters: Inner | None = None
    limit: int = 10


@pytest.mark.parametrize(
    ("req", "prefix", "expected_keys"),
    [
        # Basic: all fields fit within budget
        (
            FakeReq(project_id="p/1", filters=Inner(x=1, y=2), limit=5),
            "calls_query",
            {"calls_query.project_id", "calls_query.filters", "calls_query.limit"},
        ),
        # None values are serialized as "null"
        (
            FakeReq(project_id="p/1"),
            "test",
            {"test.project_id", "test.filters", "test.limit"},
        ),
    ],
    ids=["all_fields_fit", "none_values"],
)
def test_tag_request_basic(
    req: FakeReq,
    prefix: str,
    expected_keys: set[str],
) -> None:
    tags = tag_request(req, prefix)
    assert set(tags.keys()) == expected_keys
    # Every value must be valid JSON
    for v in tags.values():
        assert isinstance(v, str)
        json.loads(v)  # would raise on invalid JSON


def test_tag_request_drops_fields_exceeding_budget() -> None:
    """Fields that would push cumulative size past DD_TAG_MAX_LEN are dropped."""
    long_id = "x" * (DD_TAG_MAX_LEN - 10)
    req = FakeReq(project_id=long_id, filters=Inner(x=1, y=2), limit=99)
    tags = tag_request(req, "q")

    # project_id consumes nearly the entire budget; later fields should be dropped
    assert "q.project_id" in tags
    assert json.loads(tags["q.project_id"]) == long_id
    assert len(tags) < 3  # at least one field was dropped
