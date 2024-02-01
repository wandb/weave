import typing
import dataclasses
from urllib import parse

DICT_KEY_EDGE_TYPE = "key"
LIST_INDEX_EDGE_TYPE = "idx"
OBJECT_ATTRIBUTE_EDGE_TYPE = "attr"
TABLE_INDEX_EDGE_TYPE = "idx"
TABLE_COLUMN_EDGE_TYPE = "col"


def parse_local_ref_str(s: str) -> typing.Tuple[str, typing.Optional[list[str]]]:
    if "#" not in s:
        return s, None
    path, extra = s.split("#", 1)
    return path, extra.split("/")


@dataclasses.dataclass
class RefExtraTuple:
    edge_type: str
    part: str


@dataclasses.dataclass
class ParsedRef:
    scheme: str
    entity: typing.Optional[str]
    project: typing.Optional[str]
    artifact: str
    alias: str
    file_path_parts: list[str]
    ref_extra_tuples: list[RefExtraTuple]


def parse_ref_str(s: str) -> ParsedRef:
    scheme, _, path, _, _, ref_extra = parse.urlparse(s)
    entity = None
    project = None
    assert path.startswith("/")
    path = path[1:]
    path_parts = path.split("/")
    if scheme == "wandb-artifact":
        entity = path_parts[0]
        project = path_parts[1]
        path_parts = path_parts[2:]

    artifact, alias = path_parts[0].split(":")
    file_path_parts = path_parts[1:]
    ref_extra_tuples = []
    if ref_extra:
        ref_extra_parts = ref_extra.split("/")
        assert len(ref_extra_parts) % 2 == 0
        for i in range(0, len(ref_extra_parts), 2):
            edge_type = ref_extra_parts[i]
            part = ref_extra_parts[i + 1]
            ref_extra_tuples.append(RefExtraTuple(edge_type, part))

    return ParsedRef(
        scheme=scheme,
        entity=entity,
        project=project,
        artifact=artifact,
        alias=alias,
        file_path_parts=file_path_parts,
        ref_extra_tuples=ref_extra_tuples,
    )
