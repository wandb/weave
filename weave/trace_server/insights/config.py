"""Insights extraction config: the thing `config_sha256` on the signature tables names.

Every knob that changes what gets written into `intent_signatures` or
`failure_signatures` lives in one checked-in config file per space. A row stores
only the digest of that file, so the whole pipeline state is one column, and
none of it is in the sorting key.

The digest resolves every declared file reference to that file's own sha256, so
editing a taxonomy changes the config digest without anyone touching the config.
"""

import hashlib
import json
import os

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "configs")
CONFIG_SCHEMA_VERSION = 1

# Each space has exactly ONE config file, edited in place, and rows point at it
# by digest. So a digest is NOT resolvable from the working tree: it names the
# content of this file as of some commit. That is a deliberate trade. Writes are
# pinned to the deployed digest by `validate_config_sha256`, and configs only
# deploy from merged commits, so every digest that ever reached production maps
# to a commit on master and is recoverable with git. What it does not give you is
# machine resolution at read time, which is what a digest-to-content table would
# buy if a product surface ever needs to render "extracted under taxonomy v3".
SPACES = ("intent", "failure")

ConfigValue = (
    str | int | float | bool | dict[str, "ConfigValue"] | list["ConfigValue"] | None
)
Config = dict[str, ConfigValue]


def load_config(space: str) -> Config:
    """Load the checked-in config for `space` and verify its recorded digest."""
    config = _read_config(space)
    recorded = _string(_object(config, "digests"), "config_sha256")
    actual = compute_config_sha256(config)
    if recorded != actual:
        raise ValueError(
            f"{space} config digest is stale: recorded {recorded}, computed "
            f"{actual}. Run `python -m weave.trace_server.insights.config`."
        )
    return config


def compute_config_sha256(config: Config) -> str:
    """Digest the config with every file reference resolved to its own sha256.

    `digests` is excluded so the value is not self-referential, and keys are
    sorted so a reordered file produces the same digest.
    """
    resolved = _resolve_references({k: v for k, v in config.items() if k != "digests"})
    canonical = json.dumps(resolved, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_taxonomy(space: str, key: str) -> list[str]:
    """Return the label list a writer validates `category` or `severity` against."""
    reference = _object(load_section(space, "extraction"), key)
    taxonomy = _read_json(os.path.join(CONFIG_DIR, _string(reference, "path")))
    return _string_list(taxonomy, "labels")


def load_section(space: str, name: str) -> Config:
    """One top-level block of a space's config, such as `extraction` or `judge`."""
    return _object(load_config(space), name)


def read_reference(relative_path: str) -> str:
    """Read a file the config references, by its config-relative path."""
    with open(os.path.join(CONFIG_DIR, relative_path), encoding="utf-8") as handle:
        return handle.read()


def regenerate_digests() -> list[str]:
    """Rewrite each config's recorded digest in place; returns changed spaces."""
    changed = []
    for space in SPACES:
        config = _read_config(space)
        digest = compute_config_sha256(config)
        digests = _object(config, "digests")
        if digests["config_sha256"] == digest:
            continue
        digests["config_sha256"] = digest
        path = os.path.join(CONFIG_DIR, f"{space}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        changed.append(space)
    return changed


def _read_config(space: str) -> Config:
    if space not in SPACES:
        raise ValueError(f"unknown insights space {space!r}, expected one of {SPACES}")
    config = _read_json(os.path.join(CONFIG_DIR, f"{space}.json"))
    version = config["config_schema_version"]
    if version != CONFIG_SCHEMA_VERSION:
        raise ValueError(
            f"{space} config declares schema version {version}, this code reads "
            f"{CONFIG_SCHEMA_VERSION}"
        )
    # The filename decides which space a caller asked for, so a file whose own
    # `space` disagrees would silently serve one space's taxonomy under another's
    # digest.
    declared = _string(config, "space")
    if declared != space:
        raise ValueError(
            f"{space}.json declares space {declared!r}; the filename and the "
            "field must agree"
        )
    return config


def _read_json(path: str) -> Config:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_references(node: ConfigValue) -> ConfigValue:
    """Replace every {"path": ...} reference with the referenced file's sha256.

    Any `sha256` already written next to a `path` is ignored and recomputed, so
    the checked-in files carry the path alone rather than a value that looks
    authoritative and is not.
    """
    if isinstance(node, dict):
        if "path" in node:
            path = _string(node, "path")
            return {"path": path, "sha256": _file_sha256(path)}
        return {key: _resolve_references(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_resolve_references(item) for item in node]
    return node


def _file_sha256(relative_path: str) -> str:
    with open(os.path.join(CONFIG_DIR, relative_path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


# A config is arbitrary JSON so the digest can hash whatever a space declares.
# These readers narrow the one field they touch and name the file that is wrong.
def _object(config: Config, key: str) -> Config:
    value = config.get(key)
    if not isinstance(value, dict):
        raise TypeError(f"config field {key!r} must be an object, got {type(value)}")
    return value


def _string(config: Config, key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str):
        raise TypeError(f"config field {key!r} must be a string, got {type(value)}")
    return value


def _string_list(config: Config, key: str) -> list[str]:
    value = config.get(key)
    if not isinstance(value, list):
        raise TypeError(f"config field {key!r} must be a list, got {type(value)}")
    labels = [item for item in value if isinstance(item, str)]
    if len(labels) != len(value):
        raise TypeError(f"config field {key!r} must hold only strings")
    return labels


if __name__ == "__main__":
    updated = regenerate_digests()
    print(f"updated: {', '.join(updated)}" if updated else "digests already current")
