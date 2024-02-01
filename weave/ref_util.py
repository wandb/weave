import typing
import dataclasses
from urllib import parse

from . import box

DICT_KEY_EDGE_TYPE = "key"
LIST_INDEX_EDGE_TYPE = "ndx"
OBJECT_ATTRIBUTE_EDGE_TYPE = "atr"
TABLE_ROW_EDGE_TYPE = "row"
TABLE_COLUMN_EDGE_TYPE = "col"


def parse_local_ref_str(s: str) -> typing.Tuple[str, typing.Optional[list[str]]]:
    if "#" not in s:
        return s, None
    path, extra = s.split("#", 1)
    return path, extra.split("/")


def val_with_relative_ref(
    parent_object: typing.Any, child_object: typing.Any, ref_extra_parts: list[str]
) -> typing.Any:
    from . import context_state
    from . import ref_base

    # If we already have a ref, resolve it
    if isinstance(child_object, ref_base.Ref):
        child_object = child_object.get()

    # Only do this if ref_tracking_enabled right now. I just want to
    # avoid introducing new behavior into W&B prod for the moment.
    if context_state.ref_tracking_enabled():
        from . import storage

        child_ref = storage.get_ref(child_object)
        parent_ref = ref_base.get_ref(parent_object)

        # This first check is super important - if the child ref is pointing
        # to a completely different artifact (ref), then we want to point to
        # the child's inherent ref, not the relative ref from the parent.
        if child_ref is not None:
            if parent_ref is not None:
                if hasattr(child_ref, "version") and hasattr(parent_ref, "version"):
                    if child_ref.version != parent_ref.version:
                        return child_object

        if parent_ref is not None:
            child_object = box.box(child_object)
            sub_ref = parent_ref.with_extra(None, child_object, ref_extra_parts)
            ref_base._put_ref(child_object, sub_ref)
        return child_object

    return child_object


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
