"""Const value implementation.

You can use weave.const() to wrap a Python value. This tells the Weave type
system to encode the value as a Const type. E.g. as ConstType(StringType(), <val>) rather
than StringType()
"""

import typing
from . import weave_types as types


class Const:
    val: typing.Any

    def __init__(self, val: typing.Any):
        self.val = val


types.Const.instance_classes = Const


def const(obj: typing.Any) -> Const:
    """Mark a value as const so the Weave type system treats it as a ConstType"""
    return Const(obj)
