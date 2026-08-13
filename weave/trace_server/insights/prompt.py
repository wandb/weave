"""Render a signature type's judge prompt from its config.

The asset holds the wording and the config holds every value the wording shares
with the pipeline, written as a `$name`. Both are inside `config_sha`, so a
reworded prompt and a retuned history window are equally visible.
"""

from string import Template

from weave.trace_server.insights import config


def render_prompt(signature_type: str) -> str:
    """The signature type's judge prompt with every config-supplied token substituted.

    `substitute` raises `KeyError` on a token the config does not supply, which
    beats sending a judge a literal `$name`.
    """
    extraction = config.load_config(signature_type).extraction
    return Template(extraction.prompt.read().strip()).substitute(_tokens(extraction))


def _tokens(extraction: config.Extraction) -> dict[str, str]:
    """Every numeric knob as `$name`, every taxonomy as `$name_labels` and
    `$name_definitions`.

    Derived from the declared fields rather than listed, so reaching a new knob
    from an asset is a config edit and a token. An asset is free to ignore any of
    them: `substitute` only cares about the tokens it actually contains.
    """
    tokens: dict[str, str] = {}
    for name in type(extraction).model_fields:
        value = getattr(extraction, name)
        if isinstance(value, config.TaxonomyRef):
            labels = value.labels()
            tokens[f"{name}_labels"] = "|".join(label.name for label in labels)
            tokens[f"{name}_definitions"] = "\n".join(
                f"- `{label.name}`: {label.definition}" for label in labels
            )
        elif isinstance(value, int):
            tokens[name] = str(value)
    return tokens
