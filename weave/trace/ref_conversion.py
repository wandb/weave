"""Convert external weave:/// ref URIs to internal refs.

This module converts external (entity/project-scoped) ref URIs into
Internal*Ref objects that use internal project IDs.  The pipeline is:

1. convert_same_project_ref: for refs within the current project
2. convert_cross_project_ref: for refs in a foreign project (resolves via protocol)
"""

from __future__ import annotations

from typing import Protocol, overload

from weave.shared.refs_internal import (
    InternalCallRef,
    InternalObjectRef,
    InternalOpRef,
    InternalRef,
    InternalTableRef,
)
from weave.trace.refs import CallRef, ObjectRef, OpRef, Ref, TableRef


class ExternalToInternalProjectIdResolver(Protocol):
    """Resolves an external project ID (entity/project) to its internal ID."""

    def resolve_external_to_internal_project_id(
        self, ext_project_id: str
    ) -> str | None: ...


class CrossProjectRefError(Exception):
    """Raised when convert_same_project_ref receives a ref from a different project."""


class ProjectNotFoundError(Exception):
    """Raised when a cross-project ref's project cannot be resolved."""


@overload
def ext_ref_to_internal(
    ref: TableRef, internal_project_id: str
) -> InternalTableRef: ...
@overload
def ext_ref_to_internal(ref: CallRef, internal_project_id: str) -> InternalCallRef: ...
@overload
def ext_ref_to_internal(ref: OpRef, internal_project_id: str) -> InternalOpRef: ...
@overload
def ext_ref_to_internal(
    ref: ObjectRef, internal_project_id: str
) -> InternalObjectRef: ...


def ext_ref_to_internal(
    ref: ObjectRef | OpRef | TableRef | CallRef,
    internal_project_id: str,
) -> InternalRef:
    """Convert a parsed external Ref to the corresponding Internal*Ref.

    The returned object has a .uri property for the internal URI string.
    The Internal*Ref __post_init__ validates field constraints (no slashes
    in names, valid extra paths, etc.) matching server-side rules.
    """
    if isinstance(ref, TableRef):
        return InternalTableRef(
            project_id=internal_project_id,
            digest=ref.digest,
        )
    if isinstance(ref, CallRef):
        return InternalCallRef(
            project_id=internal_project_id,
            id=ref.id,
            extra=list(ref.extra),
        )
    if isinstance(ref, OpRef):
        return InternalOpRef(
            project_id=internal_project_id,
            name=ref.name,
            version=ref.digest,
            extra=list(ref.extra),
        )
    if isinstance(ref, ObjectRef):
        return InternalObjectRef(
            project_id=internal_project_id,
            name=ref.name,
            version=ref.digest,
            extra=list(ref.extra),
        )
    raise TypeError(f"Unsupported ref type: {type(ref)}")


def convert_same_project_ref(
    ref_str: str,
    ext_project_id: str,
    internal_project_id: str,
) -> InternalRef:
    """Convert a same-project external ref URI to an Internal*Ref.

    Parses ref_str via Ref.parse_uri, then builds the Internal*Ref.
    Caller can use .uri to get the string form.
    Raises CrossProjectRefError if it belongs to a different project.
    """
    ref = Ref.parse_uri(ref_str)
    ref_project_id = f"{ref.entity}/{ref.project}"
    if ref_project_id != ext_project_id:
        raise CrossProjectRefError(
            f"Ref belongs to {ref_project_id!r}, not {ext_project_id!r}: {ref_str}"
        )
    return ext_ref_to_internal(ref, internal_project_id)


def convert_cross_project_ref(
    ref_str: str,
    ext_project_id: str,
    resolver: ExternalToInternalProjectIdResolver,
) -> InternalRef:
    """Convert a cross-project external ref URI to an Internal*Ref.

    Resolves the foreign project's internal ID via the resolver, then builds
    the Internal*Ref.  Raises ProjectNotFoundError if the project cannot be resolved.
    """
    ref = Ref.parse_uri(ref_str)
    ref_project_id = f"{ref.entity}/{ref.project}"
    if ref_project_id == ext_project_id:
        raise CrossProjectRefError(
            f"Ref belongs to same project {ext_project_id!r}, "
            f"use convert_same_project_ref instead: {ref_str}"
        )

    resolved = resolver.resolve_external_to_internal_project_id(ref_project_id)
    if resolved is None:
        raise ProjectNotFoundError(
            f"Cannot resolve internal ID for project {ref_project_id!r}: {ref_str}"
        )
    return ext_ref_to_internal(ref, resolved)
