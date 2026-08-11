"""Render a space's judge prompt from its config.

The asset holds the wording and the config holds every value the wording shares
with the pipeline, written as a `$name`. Both are inside `config_sha256`, so a
reworded prompt and a retuned history window are equally visible: neither can
change what the judge sees without moving the digest a row records.
"""

from string import Template

from weave.trace_server.insights import config


def render_prompt(space: str) -> str:
    """The space's judge prompt with every config-supplied token substituted.

    `substitute` raises `KeyError` on a token the config does not supply, which
    beats sending a judge a literal `$name`.
    """
    extraction = config.load_config(space).extraction
    template = Template(extraction.prompt.read().strip())
    return template.substitute(_tokens(extraction))


def _tokens(extraction: config.Extraction) -> dict[str, str]:
    """The `$name` substitutions each space's prompt asset declares."""
    if isinstance(extraction, config.IntentExtraction):
        return {
            "history_turns": str(extraction.history_turns),
            "history_assistant_tokens": str(extraction.history_assistant_tokens),
            "max_items_per_turn": str(extraction.max_items_per_turn),
            "taxonomy_labels": _labels(extraction.taxonomy),
            "sentiment_labels": _labels(extraction.sentiment),
        }
    if isinstance(extraction, config.FailureExtraction):
        return {
            "history_turns": str(extraction.history_turns),
            "history_assistant_tokens": str(extraction.history_assistant_tokens),
            "max_failures_per_turn": str(extraction.max_failures_per_turn),
            "taxonomy_labels": _labels(extraction.taxonomy),
            "severity_labels": _labels(extraction.severity),
        }
    raise TypeError(f"no prompt token rule for {type(extraction).__name__}")


def _labels(reference: config.Reference) -> str:
    """A taxonomy rendered as the alternation the judge must choose from."""
    return "|".join(config.load_taxonomy(reference))
