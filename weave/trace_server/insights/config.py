"""Insights extraction config: the thing `config_sha256` on the signature tables names.

Every knob that changes what gets written into `intent_signatures` or
`failure_signatures` lives in one checked-in config file per space, so the whole
pipeline state is one column and none of it is in the sorting key.

The digest resolves every declared file reference to that file's own sha256, so
editing a taxonomy moves the digest without anyone touching the config.
"""

import hashlib
import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "configs")
SPACES = ("intent", "failure")


class _Strict(BaseModel):
    """Rejects undeclared keys, so a knob nothing reads cannot reach a config."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Reference(_Strict):
    """A config-relative path to a checked-in asset, digested by its content."""

    path: str

    def read(self) -> str:
        with open(os.path.join(CONFIG_DIR, self.path), encoding="utf-8") as handle:
            return handle.read()

    def sha256(self) -> str:
        with open(os.path.join(CONFIG_DIR, self.path), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()


class Taxonomy(_Strict):
    description: str
    labels: list[str]


class IntentExtraction(_Strict):
    prompt: Reference
    taxonomy: Reference
    sentiment: Reference
    history_turns: int
    max_items_per_turn: int
    current_user_tokens: int
    history_user_tokens: int
    history_assistant_tokens: int
    normalization_version: int


class FailureExtraction(_Strict):
    prompt: Reference
    taxonomy: Reference
    severity: Reference
    history_turns: int
    max_failures_per_turn: int
    current_turn_tokens: int
    history_assistant_tokens: int
    normalization_version: int


class Judge(_Strict):
    model: str
    temperature: float


class Embedding(_Strict):
    provider: str
    model: str
    dimensions: int
    output_normalization: str


class IntentConfig(_Strict):
    config_schema_version: Literal[1]
    space: Literal["intent"]
    extraction: IntentExtraction
    judge: Judge
    embedding: Embedding


class FailureConfig(_Strict):
    config_schema_version: Literal[1]
    space: Literal["failure"]
    extraction: FailureExtraction
    judge: Judge
    embedding: Embedding


SpaceConfig = IntentConfig | FailureConfig
Extraction = IntentExtraction | FailureExtraction


def load_config(space: str) -> SpaceConfig:
    """Load and validate the checked-in config for `space`."""
    if space not in _CONFIG_MODELS:
        raise ValueError(f"unknown insights space {space!r}, expected one of {SPACES}")
    path = os.path.join(CONFIG_DIR, f"{space}.json")
    with open(path, encoding="utf-8") as handle:
        return _CONFIG_MODELS[space].model_validate_json(handle.read())


def config_sha256(config: SpaceConfig) -> str:
    """Digest the config with every file reference resolved to its own sha256.

    Keys are sorted, so reordering a config file leaves the digest alone while
    editing any file it references moves it.
    """
    canonical = json.dumps(_digestible(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_taxonomy(reference: Reference) -> list[str]:
    """The label list a writer validates a categorical column against."""
    return Taxonomy.model_validate_json(reference.read()).labels


# The filename decides which space a caller asked for, and `space` is a Literal,
# so a file whose own field disagrees fails to validate rather than serving one
# space's taxonomy under another's digest.
_CONFIG_MODELS: dict[str, type[SpaceConfig]] = {
    "intent": IntentConfig,
    "failure": FailureConfig,
}


def _digestible(value: object) -> object:
    """The config as plain JSON, with each reference replaced by its content hash."""
    if isinstance(value, Reference):
        return {"path": value.path, "sha256": value.sha256()}
    if isinstance(value, BaseModel):
        return {
            name: _digestible(getattr(value, name)) for name in type(value).model_fields
        }
    return value
