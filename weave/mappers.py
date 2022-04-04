class Mapper:
    def __init__(self, type_, mapper, artifact, path):
        pass

    def result_type(self):
        raise NotImplementedError

    def apply(self, obj):
        return obj


def make_mapper(map_fn):
    def mapper(type_, artifact, path=[]):
        return map_fn(type_, mapper, artifact, path)

    return mapper
