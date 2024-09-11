# This is a concrete implemention of TaggedValue, an alternative
# representation to the tag_store.py version. This is currently
# only used in tests.

import dataclasses
import typing

from weave.legacy.weave import box
from weave.legacy.weave.language_features.tagging import tag_store


@dataclasses.dataclass
class TaggedValue:
    tag: dict[str, typing.Any]
    value: typing.Any


def concrete_to_tagstore(val: typing.Any) -> typing.Any:
    if isinstance(val, dict):
        return {k: concrete_to_tagstore(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [concrete_to_tagstore(v) for v in val]
    elif isinstance(val, TaggedValue):
        v = box.box(concrete_to_tagstore(val.value))
        tag_store.add_tags(v, concrete_to_tagstore(val.tag))
        return v
    elif dataclasses.is_dataclass(val):
        params = {
            f.name: concrete_to_tagstore(getattr(val, f.name))
            for f in dataclasses.fields(val)
        }
        return val.__class__(**params)
    return val


def concrete_from_tagstore(val: typing.Any) -> typing.Any:
    if tag_store.is_tagged(val):
        return TaggedValue(
            concrete_from_tagstore(tag_store.get_tags(val)),
            _concrete_from_tagstore_inner(val),
        )
    return _concrete_from_tagstore_inner(val)


def _concrete_from_tagstore_inner(val: typing.Any):
    if isinstance(val, dict):
        return {k: concrete_from_tagstore(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [concrete_from_tagstore(v) for v in val]
    elif dataclasses.is_dataclass(val):
        params = {
            f.name: concrete_from_tagstore(getattr(val, f.name))
            for f in dataclasses.fields(val)
        }
        return val.__class__(**params)
    return val
