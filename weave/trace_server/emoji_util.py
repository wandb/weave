import re

import emoji

RE_TONE = r"_(light|medium-light|medium|medium-dark|dark)_skin_tone"


def detone_shortcode(shortcode: str) -> str:
    """Remove any skin tone specifiers from a shortcode, if they exist."""
    return re.sub(RE_TONE, "", shortcode)


def detone_emojis(string: str) -> str:
    """Remove any skin tone modifiers from the emojis in a string."""

    def detone(matched: str, _data: dict[str, str]) -> str:
        return emoji.emojize(detone_shortcode(emoji.demojize(matched)))

    return emoji.replace_emoji(string, replace=detone)
