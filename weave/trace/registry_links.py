from __future__ import annotations

import dataclasses
import re
from typing import Protocol, TypeAlias

from weave.trace.ref_util import get_ref
from weave.trace.refs import ObjectRef


class SupportsRegistryLinkRef(Protocol):
    """Structural type for published objects that expose an attached ref."""

    ref: ObjectRef | None


RegistryLinkable: TypeAlias = SupportsRegistryLinkRef | ObjectRef | str


@dataclasses.dataclass(frozen=True)
class RegistryTargetPathParts:
    """Named parts of a registry target path."""

    registry_project: str
    portfolio_name: str


def resolve_linkable_ref(linkable: RegistryLinkable) -> ObjectRef:
    """Resolve a published Object, ObjectRef, or weave:/// URI to an ObjectRef."""
    if isinstance(linkable, ObjectRef):
        return linkable
    if isinstance(linkable, str):
        return ObjectRef.parse_uri(linkable)
    if (ref := get_ref(linkable)) is not None:
        return ref
    raise ValueError(
        "Expected a published object, ObjectRef, or weave:/// URI. "
        "Call weave.publish() first."
    )


def parse_registry_target_path(target_path: str) -> RegistryTargetPathParts:
    """Parse `<registry_project>/<portfolio_name>` into a named structure."""
    match = re.fullmatch(r"(wandb-registry-[^/]+)/([^/]+)", target_path)
    if match is None:
        raise ValueError(
            "target_path must match '<registry_project>/<portfolio_name>' "
            "where registry_project starts with 'wandb-registry-'"
        )
    registry_project, portfolio_name = match.groups()
    return RegistryTargetPathParts(
        registry_project=registry_project,
        portfolio_name=portfolio_name,
    )
