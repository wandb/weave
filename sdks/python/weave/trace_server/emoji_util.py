import re

import emoji

RE_TONE = r"_(light|medium-light|medium|medium-dark|dark)_skin_tone"


def detone_shortcode(shortcode: str) -> str:
    """Remove any skin tone specifiers from a shortcode, if they exist."""
    return re.sub(RE_TONE, "", shortcode)


def detone_emojis(string: str) -> str:
    """Remove any skin tone modifiers from the emojis in a string."""
    detoned = ""
    # Not sure why mypy can't find analyze in emoji, but it's there
    for token in emoji.analyze(string, non_emoji=True):  # type: ignore
        if isinstance(token.value, str):
            detoned += token.value
        else:
            emoji_match = token.value
            shortcode = emoji.demojize(emoji_match.emoji)
            detoned_shortcode = detone_shortcode(shortcode)
            detoned += emoji.emojize(detoned_shortcode)
    return detoned
