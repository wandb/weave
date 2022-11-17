class WeaveBaseError(Exception):
    pass


class WeaveInternalError(WeaveBaseError):
    """Internal Weave Error (a programming error)"""

    pass


class WeaveSerializeError(WeaveBaseError):
    pass


class WeaveApiError(WeaveBaseError):
    pass


class WeaveTypeError(WeaveBaseError):
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
