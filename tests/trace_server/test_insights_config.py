"""The `config_sha` contract: one digest that moves when anything upstream moves."""

import contextlib
import os
import shutil
from collections.abc import Iterator

import pytest
import yaml
from pydantic import ValidationError

from weave.trace_server.insights import config, prompt


@pytest.fixture
def config_dir(tmp_path, monkeypatch) -> str:
    """A writable copy of the checked-in configs, so tests can edit them."""
    target = str(tmp_path / "configs")
    shutil.copytree(config.CONFIG_DIR, target)
    monkeypatch.setattr(config, "CONFIG_DIR", target)
    return target


def test_signature_types_have_distinct_digests():
    """A contamination check reading topK(config_sha) must tell them apart."""
    assert _digest("intent") != _digest("failure")


def test_clustering_config_is_typed_and_content_addressed(config_dir):
    clustering = config.load_clustering_config()
    assert clustering.model_dump() == {
        "config_schema_version": 1,
        "algorithm": "hdbscan",
        "scope": "category",
        "max_clusters": 100,
        "reduction": {
            "dimensions": 15,
            "neighbors": 15,
            "min_dist": 0.0,
            "metric": "cosine",
            "random_state": 0,
            "minimum_rows": 50,
        },
        "density": {
            "min_cluster_size": 3,
            "min_samples": 3,
            "metric": "euclidean",
            "cluster_selection_method": "eom",
            "allow_single_cluster": False,
        },
        "projection": {"neighbors": 15, "min_dist": 0.0, "random_state": 0},
    }

    before = config.config_sha(clustering)
    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        raw["density"]["min_cluster_size"] = 5
    after_density_edit = config.config_sha(config.load_clustering_config())
    assert after_density_edit != before

    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        raw["reduction"]["random_state"] = 7
    assert config.config_sha(config.load_clustering_config()) not in {
        before,
        after_density_edit,
    }

    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        raw["untracked_parameter"] = True
    with pytest.raises(ValidationError, match="untracked_parameter"):
        config.load_clustering_config()

    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        raw.pop("untracked_parameter")
        raw["density"]["min_cluster_size"] = 1
    with pytest.raises(ValidationError, match="min_cluster_size"):
        config.load_clustering_config()

    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        raw["max_clusters"] = 0
    with pytest.raises(ValidationError, match="max_clusters"):
        config.load_clustering_config()


@pytest.mark.parametrize("signature_type", config.SIGNATURE_TYPES)
def test_prompt_renders_every_declared_label_and_its_definition(signature_type):
    """Every token resolves, and the taxonomy supplies both halves of a label.

    The label list reaches the judge twice: as the alternation it must choose
    from, and as the definition it reasons with. Both are generated from the one
    file, so the two cannot describe different vocabularies.
    """
    rendered = prompt.render_prompt(signature_type)
    assert "$" not in rendered

    extraction = config.load_config(signature_type).extraction
    labels = extraction.taxonomy.labels()
    assert "|".join(label.name for label in labels) in rendered
    assert all(f"- `{label.name}`: {label.definition}" in rendered for label in labels)
    assert f"up to {extraction.history_turns} " in rendered


def test_a_new_label_reaches_the_judge_without_touching_the_prompt(config_dir):
    """A label carries its own meaning, so adding one is a taxonomy edit alone.

    This is what a customer-supplied taxonomy needs: the new category reaches the
    judge as both a choosable value and a definition, and no prompt text is
    editable to get there.
    """
    with _edit_yaml(_taxonomy_path(config_dir)) as raw:
        raw["labels"].append(
            {"name": "billing_dispute", "definition": "disputes a charge."}
        )

    rendered = prompt.render_prompt("intent")
    assert "|billing_dispute" in rendered
    assert "- `billing_dispute`: disputes a charge." in rendered


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

    with _edit_yaml(os.path.join(config_dir, "intent.yaml")) as raw:
        reordered = dict(reversed(list(raw.items())))
        raw.clear()
        raw.update(reordered)
    assert _digest("intent") == before

    with _edit_yaml(_taxonomy_path(config_dir)) as raw:
        raw["labels"].append({"name": "newly_added_intent", "definition": "a new ask."})
    assert _digest("intent") != before


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (lambda raw: raw.update(config_schema_version=2), "config_schema_version"),
        (lambda raw: raw.update(signature_type="intent"), "signature_type"),
        (lambda raw: raw["extraction"].update(stop_sequences=["\n"]), "stop_sequences"),
    ],
    ids=["wrong_version", "wrong_signature_type", "undeclared_knob"],
)
def test_unloadable_configs_are_rejected_by_field(config_dir, edit, match):
    """Every failure mode names the field that is wrong, not a partial config."""
    with _edit_yaml(os.path.join(config_dir, "failure.yaml")) as raw:
        edit(raw)

    with pytest.raises(ValidationError, match=match):
        config.load_config("failure")


def test_an_unknown_signature_type_is_rejected():
    with pytest.raises(ValueError, match="unknown insights signature type"):
        config.load_config("sentiment")


def test_the_clustering_recipe_is_a_separate_digest_from_the_signature_configs():
    """A partition can be refit without re-extracting, so the two digests answer different
    questions and a reader must never see one standing in for the other.
    """
    clustering = config.load_clustering_config()
    digest = config.config_sha(clustering)

    assert digest not in {_digest("intent"), _digest("failure")}
    assert clustering.algorithm == "hdbscan"
    assert clustering.scope == "category"
    assert clustering.max_clusters == 100
    # The reduced space is what gets clustered; the projection is drawn. Separate knobs,
    # because reading the projection's neighbor count as the partition's is a real mistake.
    assert clustering.reduction.dimensions == 15
    assert clustering.reduction.neighbors == 15
    assert clustering.reduction.metric == "cosine"
    assert clustering.reduction.random_state == 0
    assert clustering.reduction.minimum_rows == 50
    assert clustering.density.min_cluster_size == clustering.density.min_samples == 3
    assert clustering.density.metric == "euclidean"


@pytest.mark.parametrize(
    ("edit", "match"),
    [
        (lambda raw: raw.update(algorithm="kmeans"), "algorithm"),
        (lambda raw: raw["reduction"].update(spectral_init=True), "spectral_init"),
        (lambda raw: raw["reduction"].pop("random_state"), "random_state"),
        (lambda raw: raw.update(config_schema_version=2), "config_schema_version"),
    ],
    ids=["unimplemented_algorithm", "undeclared_knob", "missing_seed", "wrong_version"],
)
def test_an_unloadable_clustering_recipe_is_rejected_by_field(config_dir, edit, match):
    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        edit(raw)

    with pytest.raises(ValidationError, match=match):
        config.load_clustering_config()


def test_unpinning_the_reduction_seed_moves_the_clustering_digest(config_dir):
    """An unpinned refit is a different pipeline generation, so rows must not claim the old one."""
    before = config.config_sha(config.load_clustering_config())

    with _edit_yaml(os.path.join(config_dir, "clustering.yaml")) as raw:
        raw["reduction"]["random_state"] = None
    unpinned = config.load_clustering_config()

    assert unpinned.reduction.random_state is None
    assert config.config_sha(unpinned) != before


@pytest.mark.parametrize(
    "path",
    ["../../../../etc/passwd", "/etc/passwd", "taxonomies/../../__init__.py"],
    ids=["traversal", "absolute", "escapes-after-descending"],
)
def test_a_reference_may_not_read_outside_the_config_dir(path):
    """A reference names checked-in content, so an escaping path is refused.

    Checked at read time rather than at validation, so a digest can never be taken
    over a file the config package does not own.
    """
    reference = config.Reference(path=path)

    with pytest.raises(ValueError, match="escapes"):
        reference.read_bytes()


def _digest(signature_type: str) -> str:
    return config.config_sha(config.load_config(signature_type))


def _taxonomy_path(config_dir: str) -> str:
    return os.path.join(config_dir, "taxonomies", "intent_categories.yaml")


def _append(path: str, text: str) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(text)


@contextlib.contextmanager
def _edit_yaml(path: str) -> Iterator[dict]:
    """Load a YAML file, yield it for mutation, write it back."""
    with open(path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)
    yield raw
    with open(path, "w", encoding="utf-8") as handle:
        yaml.safe_dump(raw, handle, sort_keys=False)
