from . import weave_types as types


class List(list):
    def __init__(self, items=None):
        self._obj_type = types.UnknownType()
        if items is not None:
            for item in items:
                self.add(item)

    def _ipython_display_(self):
        from . import show

        show(self)

    # TODO: do type checking on any list manipulation!? interesting...
    #     is it better to just compute the type when .type() is called instead?
    #     that certainly makes this class easier to implement as we don't have
    #     to ensure we find other possible way of updating a list. but we'd
    #     probably want to cache that result and invalidate on update so...
    # But maybe we don't need this class at all, just put all the logic in the
    #   List save() method
    def add(self, obj):
        self.append(obj)
        obj_type = types.TypeRegistry.type_of(obj)
        if obj_type is None:
            raise Exception("can't detect type for object: %s" % obj)
        next_type = self._obj_type.assign_type(obj_type)
        if isinstance(next_type, types.Invalid):
            next_type = types.UnionType(self._obj_type, obj_type)
        self._obj_type = next_type

    @property
    def type(self):
        from . import types_numpy

        # hmm... is this what we want? Have to hard code other list types
        # here?
        # TODO: no it isn't, not composable.
        if isinstance(self._obj_type, types_numpy.NumpyArrayType):
            new_shape = (len(self._items),) + self._obj_type.shape
            return types_numpy.NumpyArrayType(self._obj_type.dtype, new_shape)
        else:
            return List(self._obj_type)
