"""Insights extraction config: the thing `config_sha` on the signature tables names.

Every knob that changes what gets written into `intent_signatures` or
`failure_signatures` lives in one checked-in config file per space, so the whole
pipeline state is one column and none of it is in the sorting key. A reference
serializes as its own content hash, so editing a taxonomy or a prompt moves the
digest without anyone touching the config.
"""

import hashlib
import json
import os
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, model_serializer

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "configs")


class _Strict(BaseModel):
    """Rejects undeclared keys, so a knob nothing reads cannot reach a config."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Reference(_Strict):
    """A config-relative path to a checked-in asset, digested by its content."""

    path: str

    def read_bytes(self) -> bytes:
        with open(os.path.join(CONFIG_DIR, self.path), "rb") as handle:
            return handle.read()

    def read(self) -> str:
        return self.read_bytes().decode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.read_bytes()).hexdigest()

    @model_serializer
    def _serialize(self) -> dict[str, str]:
        """Carries the content hash, which is what makes a digest follow the file."""
        return {"path": self.path, "sha256": self.sha256()}


class _Taxonomy(_Strict):
    description: str
    labels: list[str]


class TaxonomyRef(Reference):
    """The label list a writer validates a categorical column against.

    Its own type because taxonomies are the references that render into a prompt.
    """

    def labels(self) -> list[str]:
        return _Taxonomy.model_validate_json(self.read()).labels


class Extraction(_Strict):
    """What both spaces declare. A shared knob must mean the same thing in each."""

    prompt: Reference
    taxonomy: TaxonomyRef
    history_turns: int
    history_assistant_tokens: int
    normalization_version: int


class IntentExtraction(Extraction):
    sentiment: TaxonomyRef
    max_items_per_turn: int
    # The intent judge distills the user's own message, so it budgets that turn's
    # user text; the failure judge reads the whole turn instead.
    current_user_tokens: int
    history_user_tokens: int


class FailureExtraction(Extraction):
    severity: TaxonomyRef
    max_failures_per_turn: int
    max_evidence_spans: int
    current_turn_tokens: int


class Judge(_Strict):
    model: str
    temperature: float


class Embedding(_Strict):
    provider: str
    model: str
    dimensions: int
    output_normalization: str


_E = TypeVar("_E", bound=Extraction)


class _SpaceConfig(_Strict, Generic[_E]):
    """What every space declares. `space` itself is declared per subclass."""

    config_schema_version: Literal[1]
    extraction: _E
    judge: Judge
    embedding: Embedding


# Each subclass pins `space` to a Literal, so a file whose own field disagrees
# fails to validate rather than serving one space's taxonomy under another's digest.
class IntentConfig(_SpaceConfig[IntentExtraction]):
    space: Literal["intent"]


class FailureConfig(_SpaceConfig[FailureExtraction]):
    space: Literal["failure"]


SpaceConfig = IntentConfig | FailureConfig

_CONFIG_MODELS: dict[str, type[SpaceConfig]] = {
    "intent": IntentConfig,
    "failure": FailureConfig,
}
SPACES = tuple(_CONFIG_MODELS)


def load_config(space: str) -> SpaceConfig:
    """Load and validate the checked-in config for `space`."""
    if space not in _CONFIG_MODELS:
        raise ValueError(f"unknown insights space {space!r}, expected one of {SPACES}")
    path = os.path.join(CONFIG_DIR, f"{space}.json")
    with open(path, encoding="utf-8") as handle:
        return _CONFIG_MODELS[space].model_validate_json(handle.read())


def config_sha(config: SpaceConfig) -> str:
    """Digest the config with every file reference resolved to its own sha256.

    Keys are sorted, so reordering a config file leaves the digest alone while
    editing any file it references moves it.
    """
    canonical = json.dumps(config.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
