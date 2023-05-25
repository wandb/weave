import logging
from time import time
from types import FunctionType, ModuleType
from sys import getsizeof
from gc import get_referents

class Profile:
    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        print(f"[PROFILE] {self.label}: start")
        self.start = time()

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed = time() - self.start
        print(f"[PROFILE] {self.label}: {elapsed}s")

def getsize_mb(obj):
    return f"{getsize(obj) / 1000000}MB"

SIZE_BLACKLIST = type, ModuleType, FunctionType

def getsize(obj):
    """sum size of object & members."""
    if isinstance(obj, SIZE_BLACKLIST):
        raise TypeError('getsize() does not take argument of type: '+ str(type(obj)))
    seen_ids = set()
    size = 0
    objects = [obj]
    while objects:
        need_referents = []
        for obj in objects:
            if not isinstance(obj, SIZE_BLACKLIST) and id(obj) not in seen_ids:
                seen_ids.add(id(obj))
                size += getsizeof(obj)
                need_referents.append(obj)
        objects = get_referents(*need_referents)
    return size