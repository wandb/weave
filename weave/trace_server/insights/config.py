"""Insights extraction config: the thing `config_sha` on the signature tables names.

Every knob that changes what gets written into `intent_signatures` or
`failure_signatures` lives in one checked-in config file per signature type, so the whole
pipeline state is one column and none of it is in the sorting key. A reference
serializes as its own content hash, so editing a taxonomy or a prompt moves the
digest without anyone touching the config.
"""

import hashlib
import json
import os
from typing import Generic, Literal, TypeVar

import yaml
from pydantic import BaseModel, ConfigDict, model_serializer

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "configs")


class _Strict(BaseModel):
    """Rejects undeclared keys, so a knob nothing reads cannot reach a config."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Reference(_Strict):
    """A config-relative path to a checked-in asset, digested by its raw bytes.

    Raw bytes, so a comment in a referenced file moves `config_sha` too. That errs
    toward declaring a new pipeline generation rather than silently reusing one.
    """

    path: str

    def read_bytes(self) -> bytes:
        with open(_resolve_in_config_dir(self.path), "rb") as handle:
            return handle.read()

    def read(self) -> str:
        return self.read_bytes().decode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.read_bytes()).hexdigest()

    @model_serializer
    def _serialize(self) -> dict[str, str]:
        """Carries the content hash, which is what makes a digest follow the file."""
        return {"path": self.path, "sha256": self.sha256()}


class Label(_Strict):
    """One categorical value, carrying the prose a judge needs to apply it.

    The definition lives here rather than in the prompt so that adding a label is
    one config edit, which is what a customer-supplied taxonomy will be.
    """

    name: str
    definition: str


class _Taxonomy(_Strict):
    """A taxonomy file's whole contents. Prose about the label set is a YAML comment."""

    labels: list[Label]


class TaxonomyRef(Reference):
    """The label list a writer validates a categorical column against.

    Its own type because taxonomies are the references that render into a prompt.
    """

    def labels(self) -> list[Label]:
        return _Taxonomy.model_validate(yaml.safe_load(self.read())).labels


class Extraction(_Strict):
    """What both signature types declare. A shared knob must mean the same thing in each."""

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


class _SignatureConfig(_Strict, Generic[_E]):
    """What every signature type declares. `signature_type` is declared per subclass."""

    config_schema_version: Literal[1]
    extraction: _E
    judge: Judge
    embedding: Embedding


# Each subclass pins `signature_type` to a Literal, so a file whose own field disagrees
# fails to validate rather than serving one signature type's taxonomy under another's digest.
class IntentConfig(_SignatureConfig[IntentExtraction]):
    signature_type: Literal["intent"]


class FailureConfig(_SignatureConfig[FailureExtraction]):
    signature_type: Literal["failure"]


SignatureConfig = IntentConfig | FailureConfig

_CONFIG_MODELS: dict[str, type[SignatureConfig]] = {
    "intent": IntentConfig,
    "failure": FailureConfig,
}
SIGNATURE_TYPES = tuple(_CONFIG_MODELS)


def load_config(signature_type: str) -> SignatureConfig:
    """Load and validate the checked-in config for `signature_type`."""
    if signature_type not in _CONFIG_MODELS:
        raise ValueError(
            f"unknown insights signature type {signature_type!r}, "
            f"expected one of {SIGNATURE_TYPES}"
        )
    path = os.path.join(CONFIG_DIR, f"{signature_type}.yaml")
    with open(path, encoding="utf-8") as handle:
        return _CONFIG_MODELS[signature_type].model_validate(yaml.safe_load(handle))


def config_sha(config: SignatureConfig) -> str:
    """Digest the config with every file reference resolved to its own sha256.

    Keys are sorted, so reordering a config file leaves the digest alone while
    editing any file it references moves it.
    """
    canonical = json.dumps(config.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_in_config_dir(path: str) -> str:
    """Absolute path to a config asset, rejecting any path that escapes `CONFIG_DIR`.

    A reference names checked-in content, so it may not reach the wider filesystem.
    """
    root = os.path.realpath(CONFIG_DIR)
    resolved = os.path.realpath(os.path.join(root, path))
    if os.path.commonpath([root, resolved]) != root:
        raise ValueError(f"config reference escapes {CONFIG_DIR}: {path!r}")
    return resolved
