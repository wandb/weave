from typing import Optional, Iterable


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


class WeaveConfigurationError(WeaveBaseError):
    pass


class WeaveSerializeError(WeaveBaseError):
    pass


class WeaveApiError(WeaveBaseError):
    pass


class WeaveTypeError(WeaveBaseError):
    pass


class WeaveTypeWarning(WeaveBaseWarning):
    pass


class WeaveDefinitionError(WeaveBaseError):
    pass


class WeaveMakeFunctionError(Exception):
    pass


class WeaveExpectedConstError(Exception):
    pass


class WeaveInvalidURIError(Exception):
    pass


class WeaveStorageError(Exception):
    pass


class WeaveExecutionError(Exception):
    pass


class WeavifyError(Exception):
    pass


class WeaveDispatchError(WeaveBaseError):
    pass


class WeaveArtifactFileNotFound(WeaveBaseError):
    pass


class WeaveArtifactCollectionNotFound(WeaveBaseError):
    pass


class WeaveArtifactVersionNotFound(WeaveBaseError):
    pass


class WeaveVectorizationError(WeaveBaseError):
    pass


class WeaveValueError(WeaveBaseError):
    pass


class WeaveClientArtifactResolutionFailure(WeaveBaseError):
    pass


class WeaveTableDeserializationError(WeaveBaseError):
    pass


class WeaveStitchGraphMergeError(WeaveBaseError):
    pass


class WeaveHashConstTypeError(WeaveBaseError):
    """Raised if __hash__ is called on a Const Type.

    To hash a Const Type, we'd need to hash the value, which is unbounded.
    """

    pass


class WeaveGQLCompileError(WeaveBaseError):
    pass


class WeaveGQLExecuteMissingAliasError(WeaveBaseError):
    pass


class WeaveAccessDeniedError(WeaveBaseError):
    pass


class WeaveWandbArtifactManagerError(WeaveBaseError):
    pass


class WeaveArtifactMediaFileLookupError(WeaveBaseError):
    pass


class WeaveClientRequestError(WeaveBaseError):
    pass


class WeaveMissingVariableError(WeaveBaseError):
    pass


class WeaveWBHistoryTranslationError(WeaveBaseError):
    pass


class WeaveWandbAuthenticationException(Exception):
    pass


class WeaveMissingOpDefError(WeaveBaseError):
    pass


class WeaveMergeArtifactSpecError(WeaveBaseError):
    pass
