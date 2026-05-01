from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from weave.trace.refs import ObjectRef

if TYPE_CHECKING:
    from weave.prompt.prompt import Prompt


LinkablePrompt: TypeAlias = "Prompt | ObjectRef | str"


@dataclass(frozen=True)
class RegistryTargetPathParts:
    """Named parts of a registry target path."""

    registry_project: str
    portfolio_name: str


def resolve_prompt_ref(prompt: LinkablePrompt) -> ObjectRef:
    """Resolve a published prompt, ObjectRef, or weave:/// URI to an ObjectRef."""
    if isinstance(prompt, ObjectRef):
        return prompt
    if isinstance(prompt, str):
        return ObjectRef.parse_uri(prompt)

    # Imported lazily to avoid a registry_links -> prompt -> api cycle.
    from weave.prompt.prompt import Prompt

    if isinstance(prompt, Prompt) and prompt.ref is not None:
        return prompt.ref
    raise ValueError(
        "Expected a published prompt, ObjectRef, or weave:/// URI. "
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
    return RegistryTargetPathParts(*match.groups())
