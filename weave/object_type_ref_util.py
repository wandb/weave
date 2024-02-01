import typing

from . import context_state
from . import ref_util

def make_object_getattribute(allowed_attributes: list[str]) -> typing.Callable[[typing.Any, str], typing.Any]:
    # Weave objects must auto-dereference refs when they are accessed.
    def object_getattribute(self: typing.Any, name: str) -> typing.Any:
        attribute = object.__getattribute__(self, name)
        if name not in allowed_attributes:
            return attribute
        from . import ref_base

        if isinstance(attribute, ref_base.Ref):
            # TODO: This should put a new ref as well, for ref-tracking
            attribute = attribute.get()

        # TODO: Generalize this block everywhere it's used
        # Only do this if ref_tracking_enabled right now. I just want to
        # avoid introducing new behavior into W&B prod for the moment.
        if context_state.ref_tracking_enabled():
            from . import box
            from . import storage

            attr_ref = storage.get_ref(attribute)
            self_ref = ref_base.get_ref(self)
            if attr_ref is not None:
                if self_ref is not None:
                    if attr_ref.version != self_ref.version:
                        # TODO: Comment why i am early returning here
                        return attribute

            if self_ref is not None:
                attribute = box.box(attribute)
                sub_ref = self_ref.with_extra(
                    None, attribute, [ref_util.OBJECT_ATTRIBUTE_EDGE_TYPE, str(name)]
                )
                ref_base._put_ref(attribute, sub_ref)
            return attribute

        return attribute
    return object_getattribute

def make_object_lookup_path() -> typing.Callable[[typing.Any, typing.List[str]], typing.Any]:
    def object_lookup_path(self: typing.Any, path: typing.List[str]) -> typing.Any:
        assert len(path) > 1
        edge_type = path[0]
        edge_path = path[1]
        assert edge_type == ref_util.OBJECT_ATTRIBUTE_EDGE_TYPE

        res = getattr(self, edge_path)
        remaining_path = path[2:]
        if remaining_path:
            return res._lookup_path(remaining_path)
        return res
    return object_lookup_path

def build_ref_aware_object_subclass(target_name: str, starting_class: type, allowed_attributes: list[str]) -> type:
    return type(
        target_name,
        (starting_class, ),
        {
            "__getattribute__": make_object_getattribute(allowed_attributes),
            "_lookup_path": make_object_lookup_path(),
        },
    )
