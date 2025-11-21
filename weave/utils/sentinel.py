"""Sentinel values for distinguishing 'not provided' from None or other values."""


class _NotSetType:
    """Sentinel type to distinguish 'not provided' from None or other values."""

    def __repr__(self) -> str:
        return "<NOT_SET>"


# Sentinel value to distinguish "not provided" from None
NOT_SET = _NotSetType()
