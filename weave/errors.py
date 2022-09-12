class WeaveInternalError(Exception):
    """Internal Weave Error (a programming error)"""

    pass


class WeaveSerializeError(Exception):
    pass


class WeaveApiError(Exception):
    pass


class WeaveTypeError(Exception):
    pass


class WeaveDefinitionError(Exception):
    pass


class WeaveMakeFunctionError(Exception):
    pass


class WeaveExpectedConstError(Exception):
    pass
