from .decorators import cache_control


@cache_control("list")
def list_cache_control(input_refs, result):
    return False


@cache_control("unnest")
def unnest_cache_control(input_refs, result):
    from .ops_primitives import arrow

    arr = input_refs["arr"]
    return not isinstance(arr, arrow.ArrowWeaveList)
