"""Tests for the FakeService implementation of ServiceInterface."""

from __future__ import annotations

from weave.trace_server.fake_service import FakeService
from weave.trace_server.service_interface import (
    ProjectsInfoReq,
)


def test_server_info() -> None:
    svc = FakeService()
    res = svc.server_info()
    assert res.min_required_weave_python_version == "0.0.0"
    assert res.trace_server_version == "test"


def test_ensure_project_exists() -> None:
    svc = FakeService()
    res = svc.ensure_project_exists("my-entity", "my-project")
    assert res.project_name == "my-project"


def test_projects_info() -> None:
    svc = FakeService()
    req = ProjectsInfoReq(project_ids=["entity-a/project-a", "entity-b/project-b"])
    res = svc.projects_info(req)
    assert len(res) == 2
    assert res[0].external_project_id == "entity-a/project-a"
    assert res[1].external_project_id == "entity-b/project-b"


def test_projects_info_empty() -> None:
    svc = FakeService()
    req = ProjectsInfoReq(project_ids=[])
    res = svc.projects_info(req)
    assert res == []
