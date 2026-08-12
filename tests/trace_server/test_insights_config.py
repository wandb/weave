"""The `config_sha` contract: one digest that moves when anything upstream moves."""

import contextlib
import json
import os
import shutil
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from weave.trace_server.insights import config, prompt


@pytest.fixture
def config_dir(tmp_path, monkeypatch) -> str:
    """A writable copy of the checked-in configs, so tests can edit them."""
    target = str(tmp_path / "configs")
    shutil.copytree(config.CONFIG_DIR, target)
    monkeypatch.setattr(config, "CONFIG_DIR", target)
    return target


def test_spaces_have_distinct_digests():
    """A contamination check reading topK(config_sha) must tell them apart."""
    assert _digest("intent") != _digest("failure")


@pytest.mark.parametrize("space", config.SPACES)
def test_prompt_renders_and_cannot_drift_from_its_taxonomy(space):
    """Every token resolves, and the prose describes exactly the declared labels.

    The label list reaches the judge twice: as the alternation it must choose
    from, and as the descriptions it reasons with. Only the first is generated,
    so this is what stops the second from describing a retired label.
    """
    rendered = prompt.render_prompt(space)
    assert "$" not in rendered

    extraction = config.load_config(space).extraction
    labels = extraction.taxonomy.labels()
    assert "|".join(labels) in rendered
    assert all(f"`{label}`" in rendered for label in labels)
    assert f"up to {extraction.history_turns} " in rendered


def test_editing_the_prompt_moves_the_digest(config_dir):
    """A reworded prompt is a pipeline change, so rows must stop claiming the old one."""
    before = _digest("intent")
    _append(os.path.join(config_dir, "prompts", "intent.txt"), "\nJudge on Tuesdays.\n")

    assert _digest("intent") != before


def test_a_prompt_token_the_config_does_not_supply_is_an_error(config_dir):
    """An unsubstituted token would otherwise reach the judge as literal text."""
    _append(os.path.join(config_dir, "prompts", "intent.txt"), "\nEmit $max_jokes.\n")

    with pytest.raises(KeyError, match="max_jokes"):
        prompt.render_prompt("intent")


def test_digest_follows_referenced_files_not_the_config_text(config_dir):
    """Editing a taxonomy moves the digest; reordering the config does not.

    The first half is the whole reason a reference digests by content instead of
    the config hashing its own bytes: a prompt or taxonomy edit is a pipeline
    change even though no config file was touched. The second is why it sorts keys.
    """
    before = _digest("intent")

    with _edit_json(os.path.join(config_dir, "intent.json")) as raw:
        reordered = dict(reversed(list(raw.items())))
        raw.clear()
        raw.update(reordered)
    assert _digest("intent") == before

    taxonomy = os.path.join(config_dir, "taxonomies", "intent_categories.json")
    with _edit_json(taxonomy) as raw:
        raw["labels"].append("newly_added_intent")
    assert _digest("intent") != before


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (lambda raw: raw.update(config_schema_version=2), "config_schema_version"),
        (lambda raw: raw.update(space="intent"), "space"),
        (lambda raw: raw["extraction"].update(stop_sequences=["\n"]), "stop_sequences"),
    ],
    ids=["wrong_version", "wrong_space", "undeclared_knob"],
)
def test_unloadable_configs_are_rejected_by_field(config_dir, edit, match):
    """Every failure mode names the field that is wrong, not a partial config."""
    with _edit_json(os.path.join(config_dir, "failure.json")) as raw:
        edit(raw)

    with pytest.raises(ValidationError, match=match):
        config.load_config("failure")


def test_an_unknown_space_is_rejected():
    with pytest.raises(ValueError, match="unknown insights space"):
        config.load_config("sentiment")


def _digest(space: str) -> str:
    return config.config_sha(config.load_config(space))


def _append(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


@contextlib.contextmanager
def _edit_json(path: str) -> Iterator[dict]:
    """Load a JSON file, yield it for mutation, write it back."""
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    yield raw
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(raw, handle, indent=2)
