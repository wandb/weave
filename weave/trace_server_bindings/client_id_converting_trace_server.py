from __future__ import annotations

from typing import Optional

from weave.trace_server import (
    external_to_internal_trace_server_adapter as tsi_adapter,
    trace_server_interface as tsi,
)


class FixedIdConverter(tsi_adapter.IdConverter):
    """Client-side IdConverter using fixed project/run mapping resolved at init.

    - external_project_id: "entity/project"
    - internal_project_id: server-side internal project ID
    - run_id_separator: separator between internal project id and run name
    """

    def __init__(
        self,
        external_project_id: str,
        internal_project_id: str,
        run_id_separator: str = ":",
    ) -> None:
        self._external_project_id = external_project_id
        self._internal_project_id = internal_project_id
        self._run_sep = run_id_separator

    def ext_to_int_project_id(self, project_id: str) -> str:
        # Accept either external (entity/project) or already-internal
        if project_id == self._external_project_id:
            return self._internal_project_id
        if project_id == self._internal_project_id:
            return project_id
        raise ValueError(
            f"Invalid project ID: expected '{self._external_project_id}', got '{project_id}'"
        )

    def int_to_ext_project_id(self, project_id: str) -> Optional[str]:
        # Accept either internal or external and return external if matches
        if project_id == self._internal_project_id:
            return self._external_project_id
        if project_id == self._external_project_id:
            return self._external_project_id
        return None

    def ext_to_int_run_id(self, run_id: str) -> str:
        parts = run_id.split("/")
        if len(parts) != 3:
            raise ValueError(
                "Run ID should be in the format <entity>/<project>/<run>"
            )
        entity, project, run = parts
        if f"{entity}/{project}" != self._external_project_id:
            raise ValueError(
                f"Invalid run project: expected '{self._external_project_id}', got '{entity}/{project}'"
            )
        return f"{self._internal_project_id}{self._run_sep}{run}"

    def int_to_ext_run_id(self, run_id: str) -> str:
        parts = run_id.split(self._run_sep)
        if len(parts) != 2:
            raise ValueError(
                "Internal run ID should be in the format <project_id><sep><run>"
            )
        project_id, run = parts
        if project_id != self._internal_project_id:
            raise ValueError(
                "Internal run ID does not belong to this client's project"
            )
        return f"{self._external_project_id}/{run}"

    def ext_to_int_user_id(self, user_id: str) -> str:
        return user_id

    def int_to_ext_user_id(self, user_id: str) -> str:
        return user_id


def wrap_with_id_conversion(
    internal_server: tsi.FullTraceServerInterface,
    converter: tsi_adapter.IdConverter,
) -> tsi.FullTraceServerInterface:
    """Wrap a server with external<->internal conversion using provided converter."""
    return tsi_adapter.ExternalTraceServer(internal_server, converter)
