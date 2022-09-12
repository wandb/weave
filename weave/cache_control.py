from .decorators import cache_control


@cache_control("list")
def list_cache_control(**l):
    return len(l) > 1


@cache_control("unnest")
def unnest_cache_control(arr):
    return False
