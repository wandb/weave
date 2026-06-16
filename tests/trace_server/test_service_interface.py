"""Tests for the FakeService implementation of ServiceInterface."""

from __future__ import annotations

import pytest

from weave.trace_server.fake_service import FakeService
from weave.trace_server.service_interface import (
    ProjectsInfoReq,
)


def test_server_info_and_ensure_project_exists() -> None:
    svc = FakeService()

    info = svc.server_info()
    assert info.min_required_weave_python_version == "0.0.0"
    assert info.trace_server_version == "test"

    ensured = svc.ensure_project_exists("my-entity", "my-project")
    assert ensured.project_name == "my-project"


@pytest.mark.parametrize(
    ("project_ids", "expected"),
    [
        (
            ["entity-a/project-a", "entity-b/project-b"],
            ["entity-a/project-a", "entity-b/project-b"],
        ),
        ([], []),
    ],
    ids=["populated", "empty"],
)
def test_projects_info(project_ids: list[str], expected: list[str]) -> None:
    svc = FakeService()
    res = svc.projects_info(ProjectsInfoReq(project_ids=project_ids))
    assert [p.external_project_id for p in res] == expected
