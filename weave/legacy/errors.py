from typing import Iterable, Optional


class WeaveUnmergableArtifactsError(Exception):
    pass


class WeaveFingerprintErrorMixin:
    fingerprint: Optional[Iterable] = None


class WeaveBaseError(Exception, WeaveFingerprintErrorMixin):
    pass


class WeaveBaseWarning(Warning):
    pass

# Only use this if you actually want to return an Http 400
# to the client. This should only happen in cases where the
# client is wrong.
class WeaveBadRequest(WeaveBaseError):
    pass


class WeaveInternalError(WeaveBaseError):
    """Internal Weave Error (a programming error)"""

    pass

class WeaveSerializeError(WeaveBaseError):
    pass
