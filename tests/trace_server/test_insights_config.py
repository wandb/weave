"""The `config_sha256` contract: one digest that moves when anything upstream moves."""

import json
import os
import shutil

import pytest
from pydantic import ValidationError

from weave.trace_server.insights import config, prompt

# The exact label sets the `category` Enum carried before the signature tables
# replaced it. Dropping the Enum moved enforcement to the writer; it must not
# also have quietly dropped labels. A retired label may leave the taxonomy, but
# only by being named in the moves below, so a vocabulary change stays a decision
# rather than becoming a silent drop.
_RETIRED_INTENT_LABELS = {
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
_RETIRED_FAILURE_LABELS = {
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

# Retired label -> the labels that carry it now. `feedback` splits because the two
# polarities cluster separately; `correction` and `clarification` merge because the
# boundary between contradiction and added detail was label noise. The two failure
# renames drop a propriety claim the judge cannot make without seeing the customer's
# capability limits or safety policy.
_INTENT_MOVES = {
    "feedback": ("positive_feedback", "negative_feedback"),
    "correction": ("refinement",),
    "clarification": ("refinement",),
}
_FAILURE_MOVES = {
    "improper_refusal": ("refusal",),
    "safety_violation": ("unsafe_behavior",),
}


@pytest.fixture
def config_dir(tmp_path, monkeypatch) -> str:
    """A writable copy of the checked-in configs, so tests can edit them."""
    target = str(tmp_path / "configs")
    shutil.copytree(config.CONFIG_DIR, target)
    monkeypatch.setattr(config, "CONFIG_DIR", target)
    return target


def _taxonomy(space: str) -> list[str]:
    return config.load_taxonomy(config.load_config(space).extraction.taxonomy)


def _digest(space: str) -> str:
    return config.config_sha256(config.load_config(space))


@pytest.mark.parametrize(
    ("space", "retired", "moves"),
    [
        ("intent", _RETIRED_INTENT_LABELS, _INTENT_MOVES),
        ("failure", _RETIRED_FAILURE_LABELS, _FAILURE_MOVES),
    ],
)
def test_taxonomies_account_for_every_retired_enum_label(space, retired, moves):
    """Exactly the documented moves may leave the taxonomy.

    An undocumented drop fails here, and so does a move entry for a label that is
    still present.
    """
    labels = set(_taxonomy(space))
    assert retired - labels == set(moves)
    for replacements in moves.values():
        assert set(replacements) <= labels

    # Distinct spaces must never collide, or a contamination check reading
    # topK(config_sha256) cannot tell two pipelines apart.
    assert _digest("intent") != _digest("failure")


@pytest.mark.parametrize("space", ["intent", "failure"])
def test_prompt_renders_and_cannot_drift_from_its_taxonomy(space):
    """Every token resolves, and the prose describes exactly the declared labels.

    The label list reaches the judge twice: as the alternation it must choose
    from, and as the descriptions it reasons with. Only the first is generated,
    so this is what stops the second from describing a retired label.
    """
    rendered = prompt.render_prompt(space)
    assert "$" not in rendered

    labels = _taxonomy(space)
    assert "|".join(labels) in rendered
    assert all(f"`{label}`" in rendered for label in labels)

    extraction = config.load_config(space).extraction
    assert f"up to {extraction.history_turns} " in rendered


def test_editing_the_prompt_moves_the_digest(config_dir):
    """A reworded prompt is a pipeline change, so rows must stop claiming the old one."""
    before = _digest("intent")
    with open(
        os.path.join(config_dir, "prompts", "intent.txt"), "a", encoding="utf-8"
    ) as handle:
        handle.write("\nJudge nothing on Tuesdays.\n")

    assert _digest("intent") != before


def test_a_prompt_token_the_config_does_not_supply_is_an_error(config_dir):
    """An unsubstituted token would otherwise reach the judge as literal text."""
    with open(
        os.path.join(config_dir, "prompts", "intent.txt"), "a", encoding="utf-8"
    ) as handle:
        handle.write("\nEmit at most $max_jokes jokes.\n")

    with pytest.raises(KeyError, match="max_jokes"):
        prompt.render_prompt("intent")


def test_digest_follows_referenced_files_not_the_config_text(config_dir):
    """Editing a taxonomy moves the digest; reordering the config does not.

    The first half is the whole reason the digest resolves references instead of
    hashing the config bytes: a prompt or taxonomy edit is a pipeline change even
    though no config file was touched. The second half is why it canonicalizes.
    """
    before = _digest("intent")

    config_path = os.path.join(config_dir, "intent.json")
    with open(config_path, encoding="utf-8") as handle:
        original = json.load(handle)
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(dict(reversed(list(original.items()))), handle, indent=2)
    assert _digest("intent") == before

    taxonomy_path = os.path.join(config_dir, "taxonomies", "intent_categories.json")
    with open(taxonomy_path, encoding="utf-8") as handle:
        taxonomy = json.load(handle)
    taxonomy["labels"].append("newly_added_intent")
    with open(taxonomy_path, "w", encoding="utf-8") as handle:
        json.dump(taxonomy, handle, indent=2)

    assert _digest("intent") != before


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        ({"config_schema_version": 2}, "config_schema_version"),
        # The filename decides which space a caller asked for, so a file whose own
        # `space` disagrees would serve one space's taxonomy under another's digest.
        ({"space": "intent"}, "space"),
        # An undeclared knob is rejected at load rather than reaching a judge that
        # has no token for it, or a writer that never reads it.
        ({"extraction": {"stop_sequences": ["\n\n"]}}, "stop_sequences"),
    ],
)
def test_unloadable_configs_are_rejected_by_field(config_dir, edit, match):
    """Every failure mode names the field that is wrong, not a partial config."""
    config_path = os.path.join(config_dir, "failure.json")
    with open(config_path, encoding="utf-8") as handle:
        raw = json.load(handle)
    for key, value in edit.items():
        if isinstance(value, dict):
            raw[key].update(value)
        else:
            raw[key] = value
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(raw, handle, indent=2)

    with pytest.raises(ValidationError, match=match):
        config.load_config("failure")


def test_an_unknown_space_is_rejected():
    with pytest.raises(ValueError, match="unknown insights space"):
        config.load_config("sentiment")
