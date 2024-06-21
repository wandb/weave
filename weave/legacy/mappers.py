import typing

if typing.TYPE_CHECKING:
    from weave import weave_types as types
    from weave.legacy import artifact_local


class Mapper:
    def __init__(self, type_, mapper, artifact, path):
        self.type = type_

    def result_type(self):
        raise NotImplementedError

    def apply(self, obj) -> typing.Union[dict, typing.Any]:
        return obj


def make_mapper(map_fn):
    def mapper(type_, artifact, path=[], mapper_options=None):
        return map_fn(type_, mapper, artifact, path, mapper_options=mapper_options)

    return mapper
