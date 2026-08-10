"""The `config_sha256` contract: one digest that moves when anything upstream moves."""

import json
import os
import shutil

import pytest

from weave.trace_server.insights import config

# The exact label sets the `category` Enum carried before the signature tables
# replaced it. Dropping the Enum moved enforcement to the writer; it must not
# also have quietly dropped labels.
_ENUM_INTENT_LABELS = {
    "action_request",
    "information_request",
    "problem_report",
    "feedback",
    "approval",
    "rejection",
    "correction",
    "clarification",
    "bad_faith",
    "other",
}
_ENUM_FAILURE_LABELS = {
    "task_misunderstanding",
    "context_loss",
    "wrong_output",
    "requirement_violation",
    "tool_misuse",
    "tool_failure",
    "system_error",
    "unproductive_loop",
    "capability_gap",
    "improper_refusal",
    "safety_violation",
    "other",
}


@pytest.fixture
def config_dir(tmp_path, monkeypatch) -> str:
    """A writable copy of the checked-in configs, so tests can edit them."""
    target = str(tmp_path / "configs")
    shutil.copytree(config.CONFIG_DIR, target)
    monkeypatch.setattr(config, "CONFIG_DIR", target)
    return target


@pytest.mark.parametrize(
    ("space", "expected_labels"),
    [("intent", _ENUM_INTENT_LABELS), ("failure", _ENUM_FAILURE_LABELS)],
)
def test_checked_in_configs_are_current(space, expected_labels):
    """Recorded digests match, and the taxonomy still covers every retired Enum label.

    This is the CI gate as a test: a config whose digest was not regenerated
    fails here rather than shipping rows that point at a value nothing produces.
    """
    loaded = config.load_config(space)
    assert loaded["digests"]["config_sha256"] == config.compute_config_sha256(loaded)
    assert set(config.load_taxonomy(space, "taxonomy")) == expected_labels
    # Distinct spaces must never collide, or a contamination check reading
    # topK(config_sha256) cannot tell two pipelines apart.
    assert (
        loaded["digests"]["config_sha256"]
        != config.load_config("failure" if space == "intent" else "intent")["digests"][
            "config_sha256"
        ]
    )


def test_digest_follows_referenced_files_not_the_config_text(config_dir):
    """Editing a taxonomy moves the digest; reordering the config does not.

    The first half is the whole reason the digest resolves references instead of
    hashing the config bytes: a prompt or taxonomy edit is a pipeline change even
    though no config file was touched. The second half is why it canonicalizes.
    """
    before = config.compute_config_sha256(config.load_config("intent"))

    config_path = os.path.join(config_dir, "intent.json")
    with open(config_path, encoding="utf-8") as handle:
        original = json.load(handle)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(dict(reversed(list(original.items()))), handle, indent=2)
    assert config.compute_config_sha256(config.load_config("intent")) == before

    taxonomy_path = os.path.join(config_dir, "taxonomies", "intent_categories.json")
    with open(taxonomy_path, encoding="utf-8") as handle:
        taxonomy = json.load(handle)
    taxonomy["labels"].append("newly_added_intent")
    with open(taxonomy_path, "w", encoding="utf-8") as handle:
        json.dump(taxonomy, handle, indent=2)

    after = config.compute_config_sha256(config._read_config("intent"))
    assert after != before
    # And the stale recorded digest is now loudly wrong rather than silently
    # describing a taxonomy that no longer exists.
    with pytest.raises(ValueError, match="digest is stale"):
        config.load_config("intent")
    assert config.regenerate_digests() == ["intent"]
    assert config.load_config("intent")["digests"]["config_sha256"] == after


def test_unknown_space_and_schema_version_are_rejected(config_dir):
    """Both failure modes name what went wrong instead of returning a partial config."""
    with pytest.raises(ValueError, match="unknown insights space"):
        config.load_config("sentiment")

    config_path = os.path.join(config_dir, "failure.json")
    with open(config_path, encoding="utf-8") as handle:
        raw = json.load(handle)
    raw["config_schema_version"] = config.CONFIG_SCHEMA_VERSION + 1
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(raw, handle, indent=2)

    with pytest.raises(ValueError, match="declares schema version"):
        config.load_config("failure")
