class Mapper:
    def __init__(self, type_, mapper, artifact, path):
        pass

    def result_type(self):
        raise NotImplementedError

    def apply(self, obj):
        return obj


class ChainMapper(Mapper):
    def __init__(self, serializers):
        self._serializers = serializers

    def result_type(self):
        return self._serializers[-1].result_type()

    def apply(self, obj):
        for serializer in self._serializers:
            obj = serializer.apply(obj)
        return obj


def make_mapper(map_fn):
    def mapper(type_, artifact, path=[]):
        serializers = []
        while True:
            ser = map_fn(type_, mapper, artifact, path)
            if ser is None:
                break
            next_type = ser.result_type()
            serializers.append(ser)
            if type_.__class__ == next_type.__class__:
                # If it returned the same type of type, just break to
                # avoid loop.
                # TODO: this is weird
                break
            type_ = next_type
        if not serializers:
            return None
        if len(serializers) > 1:
            return ChainMapper(serializers)
        return serializers[0]

    return mapper
