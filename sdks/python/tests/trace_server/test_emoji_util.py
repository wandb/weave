from weave.trace_server.emoji_util import detone_emojis, detone_shortcode

SHORTCODE_NO_ZWJ_NO_TONE = ":pool_8_ball:"
SHORTCODE_NO_ZWJ_TONE = ":thumbs_up_medium-dark_skin_tone:"
SHORTCODE_ZWJ_ONE_TONE = ":judge_medium-light_skin_tone:"
SHORTCODE_ZWJ_MULTIPLE_TONES = ":handshake_dark_skin_tone_medium_skin_tone:"

EMOJI_8_BALL = "🎱"
EMOJI_THUMBS_UP_TONE = "👍🏾"
EMOJI_THUMBS_UP_NO_TONE = "👍"
EMOJI_JUDGE_TONE = "🧑🏼‍⚖️"
EMOJI_JUDGE_NO_TONE = "🧑‍⚖️"
EMOJI_HANDSHAKE_TONES = "🫱🏿‍🫲🏽"
EMOJI_HANDSHAKE_NO_TONES = "🤝"

SENTENCE_TONES = f"The {EMOJI_JUDGE_TONE} had us {EMOJI_HANDSHAKE_TONES}."
SENTENCE_NO_TONES = f"The {EMOJI_JUDGE_NO_TONE} had us {EMOJI_HANDSHAKE_NO_TONES}."


def test_detone_shortcode() -> None:
    assert detone_shortcode(SHORTCODE_NO_ZWJ_NO_TONE) == ":pool_8_ball:"
    assert detone_shortcode(SHORTCODE_NO_ZWJ_TONE) == ":thumbs_up:"
    assert detone_shortcode(SHORTCODE_ZWJ_ONE_TONE) == ":judge:"
    assert detone_shortcode(SHORTCODE_ZWJ_MULTIPLE_TONES) == ":handshake:"


def test_detone_emoji() -> None:
    assert detone_emojis(EMOJI_8_BALL) == EMOJI_8_BALL
    assert detone_emojis(EMOJI_THUMBS_UP_TONE) == EMOJI_THUMBS_UP_NO_TONE
    assert detone_emojis(EMOJI_JUDGE_TONE) == EMOJI_JUDGE_NO_TONE
    assert detone_emojis(EMOJI_HANDSHAKE_TONES) == EMOJI_HANDSHAKE_NO_TONES
    assert detone_emojis(SENTENCE_TONES) == SENTENCE_NO_TONES
