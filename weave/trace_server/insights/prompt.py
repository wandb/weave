"""Render a space's judge prompt from its config.

The asset holds the wording and the config holds every value the wording shares
with the pipeline, written as a `%%TOKEN%%`. Both are inside `config_sha256`, so
a reworded prompt and a retuned history window are equally visible: neither can
change what the judge sees without moving the digest a row records.

Tokens are derived from the `extraction` block rather than listed here, so a new
knob is a config edit plus a token, never a change to this file.
"""

import re

from weave.trace_server.insights import config

# A token that survives rendering means the asset asks for something the config
# does not declare. Failing here beats sending a judge a literal `%%...%%`.
_TOKEN_PATTERN = re.compile(r"%%\w+%%")


def render_prompt(space: str) -> str:
    """The space's judge prompt with every config-supplied token substituted."""
    extraction = config.load_section(space, "extraction")
    text = config.read_reference(_prompt_path(space, extraction)).strip()
    for token, value in _tokens(space, extraction).items():
        text = text.replace(token, value)
    unresolved = sorted(set(_TOKEN_PATTERN.findall(text)))
    if unresolved:
        raise ValueError(
            f"{space} prompt has tokens the config does not supply: "
            f"{', '.join(unresolved)}"
        )
    return text


def _prompt_path(space: str, extraction: config.Config) -> str:
    prompt = extraction.get("prompt")
    # Bound to a local so the narrowing survives into the return: the subscript
    # is typed as the whole ConfigValue union, the local is not.
    path = prompt.get("path") if isinstance(prompt, dict) else None
    if not isinstance(path, str):
        raise TypeError(f"{space} config declares no prompt file reference")
    return path


def _tokens(space: str, extraction: config.Config) -> dict[str, str]:
    """`%%KEY%%` for each number, `%%KEY_LABELS%%` for each taxonomy reference."""
    tokens: dict[str, str] = {}
    for key, value in extraction.items():
        if key == "prompt" or isinstance(value, bool):
            continue
        if isinstance(value, int):
            tokens[f"%%{key.upper()}%%"] = str(value)
        elif isinstance(value, dict) and "path" in value:
            tokens[f"%%{key.upper()}_LABELS%%"] = "|".join(
                config.load_taxonomy(space, key)
            )
        else:
            # Silently skipping would surface later as the misleading "prompt has
            # tokens the config does not supply", naming the asset rather than
            # the knob that has no token rule.
            raise TypeError(
                f"{space} config key {key!r} has type {type(value).__name__}, which "
                "has no prompt token rule; add one here or move the key out of "
                "`extraction`"
            )
    return tokens
