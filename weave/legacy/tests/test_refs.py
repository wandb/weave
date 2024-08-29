import pytest

import weave
from weave.flow.obj import Object
from weave.legacy.weave import artifact_local, storage
from weave.legacy.weave import ops_arrow as arrow
from weave.trace import ref_util
from weave.trace_server.refs_internal import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
)


def test_laref_artifact_version_1():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "obj")
    assert str(ref) == "local-artifact:///my-art:v19/obj"

    print("STR", str(ref))
    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "obj"
    assert parsed_ref.extra is None

    assert ref.local_ref_str() == "obj"
    assert ref_util.parse_local_ref_str("obj") == ("obj", None)


def test_laref_artifact_version_path():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "x.txt")
    assert str(ref) == "local-artifact:///my-art:v19/x.txt"

    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "x.txt"
    assert parsed_ref.extra is None

    assert ref.local_ref_str() == "x.txt"
    assert ref_util.parse_local_ref_str("x.txt") == (
        "x.txt",
        None,
    )


def test_laref_artifact_version_path_extra1():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "x.txt", extra=["5"])
    assert str(ref) == "local-artifact:///my-art:v19/x.txt#5"

    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "x.txt"
    assert parsed_ref.extra == ["5"]

    assert ref.local_ref_str() == "x.txt#5"
    assert ref_util.parse_local_ref_str("x.txt#5") == (
        "x.txt",
        ["5"],
    )


def test_laref_artifact_version_path_obj_extra1():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "obj", extra=["5"])
    assert str(ref) == "local-artifact:///my-art:v19/obj#5"

    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "obj"
    assert parsed_ref.extra == ["5"]

    assert ref.local_ref_str() == "obj#5"
    assert ref_util.parse_local_ref_str("obj#5") == (
        "obj",
        ["5"],
    )


def test_laref_artifact_version_path_extra2():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "x.txt", extra=["5", "a"])
    assert str(ref) == "local-artifact:///my-art:v19/x.txt#5/a"

    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "x.txt"
    assert parsed_ref.extra == ["5", "a"]

    assert ref.local_ref_str() == "x.txt#5/a"
    assert ref_util.parse_local_ref_str("x.txt#5/a") == (
        "x.txt",
        ["5", "a"],
    )


"""

* Dict
    * Key
* List
    * Index
* Object
    * Attribute
* Table (ArrowWeaveList)
    * Index
    * Column
    * Id (not implemented)

"""


def assert_local_ref(object, path_parts, extra_parts):
    obj_ref = storage.get_ref(object)
    parsed_obj_ref = ref_util.parse_ref_str(obj_ref.uri)

    target_obj_ref = ref_util.ParsedRef(
        scheme="local-artifact",
        entity=None,
        project=None,
        artifact=obj_ref.name,
        alias=obj_ref.version,
        file_path_parts=path_parts,
        ref_extra_tuples=[
            ref_util.RefExtraTuple(*extra_parts[i : i + 2])
            for i in range(0, len(extra_parts), 2)
        ],
    )
    assert parsed_obj_ref == target_obj_ref


def test_ref_parser():
    assert ref_util.parse_ref_str(
        "local-artifact:///art_name:version"
    ) == ref_util.ParsedRef(
        scheme="local-artifact",
        entity=None,
        project=None,
        artifact="art_name",
        alias="version",
        file_path_parts=[],
        ref_extra_tuples=[],
    )
    assert ref_util.parse_ref_str(
        "local-artifact:///art_name:version/possibly/deep/path"
    ) == ref_util.ParsedRef(
        scheme="local-artifact",
        entity=None,
        project=None,
        artifact="art_name",
        alias="version",
        file_path_parts=["possibly", "deep", "path"],
        ref_extra_tuples=[],
    )
    assert ref_util.parse_ref_str(
        "local-artifact:///art_name:version/possibly/deep/path#very/deep/ref/extra"
    ) == ref_util.ParsedRef(
        scheme="local-artifact",
        entity=None,
        project=None,
        artifact="art_name",
        alias="version",
        file_path_parts=["possibly", "deep", "path"],
        ref_extra_tuples=[
            ref_util.RefExtraTuple("very", "deep"),
            ref_util.RefExtraTuple("ref", "extra"),
        ],
    )
    assert ref_util.parse_ref_str(
        "wandb-artifact:///entity/project/art_name:version"
    ) == ref_util.ParsedRef(
        scheme="wandb-artifact",
        entity="entity",
        project="project",
        artifact="art_name",
        alias="version",
        file_path_parts=[],
        ref_extra_tuples=[],
    )
    assert ref_util.parse_ref_str(
        "wandb-artifact:///entity/project/art_name:version/possibly/deep/path"
    ) == ref_util.ParsedRef(
        scheme="wandb-artifact",
        entity="entity",
        project="project",
        artifact="art_name",
        alias="version",
        file_path_parts=["possibly", "deep", "path"],
        ref_extra_tuples=[],
    )
    assert ref_util.parse_ref_str(
        "wandb-artifact:///entity/project/art_name:version/possibly/deep/path#very/deep/ref/extra"
    ) == ref_util.ParsedRef(
        scheme="wandb-artifact",
        entity="entity",
        project="project",
        artifact="art_name",
        alias="version",
        file_path_parts=["possibly", "deep", "path"],
        ref_extra_tuples=[
            ref_util.RefExtraTuple("very", "deep"),
            ref_util.RefExtraTuple("ref", "extra"),
        ],
    )


def test_ref_extra_dict(ref_tracking):
    obj = {"a": 1}
    saved_obj = weave.use(weave.save(obj))

    assert saved_obj == obj
    assert_local_ref(saved_obj, ["obj"], [])
    assert storage.get(saved_obj._ref.uri) == obj

    val = saved_obj["a"]
    assert val == 1
    assert_local_ref(val, ["obj"], [DICT_KEY_EDGE_NAME, "a"])
    assert storage.get(val._ref.uri) == 1


def test_ref_extra_list(ref_tracking):
    obj = [1]
    saved_obj = weave.use(weave.save(obj))

    assert saved_obj == obj
    assert_local_ref(saved_obj, ["obj"], [])
    assert storage.get(saved_obj._ref.uri) == obj

    val = saved_obj[0]
    assert val == 1
    assert_local_ref(val, ["obj"], [LIST_INDEX_EDGE_NAME, "0"])
    assert storage.get(val._ref.uri) == 1


def make_custom_object_classes_classic_type():
    @weave.type()
    class CustomObjectA:
        inner_a: int

    @weave.type()
    class CustomObjectB:
        inner_b: CustomObjectA

    return CustomObjectA, CustomObjectB


def make_custom_object_classes_pydantic():
    class CustomObjectA(Object):
        inner_a: int

    class CustomObjectB(Object):
        inner_b: CustomObjectA

    return CustomObjectA, CustomObjectB


@pytest.mark.parametrize(
    "get_custom_object_classes",
    [make_custom_object_classes_classic_type, make_custom_object_classes_pydantic],
)
def test_ref_extra_object(ref_tracking, get_custom_object_classes):
    CustomObjectA, CustomObjectB = get_custom_object_classes()

    obj = CustomObjectA(inner_a=1)
    saved_obj = weave.use(weave.save(obj))

    assert_local_ref(saved_obj, ["obj"], [])

    val = saved_obj.inner_a
    assert val == 1
    assert_local_ref(val, ["obj"], [OBJECT_ATTR_EDGE_NAME, "inner_a"])
    assert storage.get(val._ref.uri) == 1


def test_ref_extra_table(ref_tracking):
    arrow_raw = arrow.to_arrow(
        [
            {"a": 1},
            {"a": 2},
        ]
    )
    saved_obj = weave.use(weave.save(arrow_raw))

    assert saved_obj.to_pylist_notags() == arrow_raw.to_pylist_notags()
    assert_local_ref(saved_obj, ["obj"], [])
    assert (
        storage.get(saved_obj._ref.uri).to_pylist_notags()
        == arrow_raw.to_pylist_notags()
    )

    val = saved_obj[0]
    assert val == {"a": 1}
    assert_local_ref(val, ["obj"], ["row", "0"])
    assert storage.get(val._ref.uri) == {"a": 1}

    val = saved_obj.column("a")
    assert val.to_pylist_notags() == [1, 2]
    assert_local_ref(val, ["obj"], ["col", "a"])
    assert storage.get(val._ref.uri).to_pylist_notags() == [1, 2]


@pytest.mark.parametrize(
    "get_custom_object_classes",
    [make_custom_object_classes_classic_type, make_custom_object_classes_pydantic],
)
def test_ref_extra_table_very_nested(ref_tracking, get_custom_object_classes):
    CustomObjectA, CustomObjectB = get_custom_object_classes()

    arrow_raw = arrow.to_arrow(
        [
            {
                "a": arrow.to_arrow(
                    [
                        [CustomObjectA(inner_a=1)],
                    ]
                )
            },
        ]
    )

    saved_obj = weave.use(weave.save(arrow_raw))

    assert saved_obj.to_pylist_notags() == arrow_raw.to_pylist_notags()

    val = saved_obj[0]["a"][0][0].inner_a
    assert val == 1
    assert_local_ref(
        val,
        ["obj"],
        [
            "row",
            "0",
            DICT_KEY_EDGE_NAME,
            "a",
            "row",
            "0",
            LIST_INDEX_EDGE_NAME,
            "0",
            OBJECT_ATTR_EDGE_NAME,
            "inner_a",
        ],
    )
    assert storage.get(val._ref.uri) == 1


def test_refs_across_artifacts(ref_tracking):
    inner_obj = {"a": 1}
    saved_inner_obj = weave.use(weave.save(inner_obj))
    outer_obj = {"outer": inner_obj, "inner": saved_inner_obj}
    saved_outer_obj = weave.use(weave.save(outer_obj))
    obj = {"outer": inner_obj, "inner": {"a": 1}}

    # TODO: These need to be uncommented as they highlight an issue with nested refs
    # assert saved_outer_obj == obj
    assert_local_ref(saved_outer_obj, ["obj"], [])
    # assert storage.get(saved_outer_obj._ref.uri) == obj

    # Non-saved children follow the same ref structure
    val = saved_outer_obj["outer"]
    assert val == inner_obj
    assert_local_ref(val, ["obj"], [DICT_KEY_EDGE_NAME, "outer"])
    assert storage.get(val._ref.uri) == inner_obj

    val = saved_outer_obj["outer"]["a"]
    assert val == 1
    assert_local_ref(
        val, ["obj"], [DICT_KEY_EDGE_NAME, "outer", DICT_KEY_EDGE_NAME, "a"]
    )
    assert storage.get(val._ref.uri) == 1

    # Jumping artifact boundaries uses new artifact refs
    val = saved_outer_obj["inner"]
    # assert val == inner_obj
    assert_local_ref(val, ["obj"], [])
    assert storage.get(val._ref.uri) == inner_obj

    val = saved_outer_obj["inner"]["a"]
    # assert val == inner_obj
    assert_local_ref(val, ["obj"], [DICT_KEY_EDGE_NAME, "a"])
    assert storage.get(val._ref.uri) == 1


@pytest.mark.parametrize(
    "get_custom_object_classes",
    [make_custom_object_classes_classic_type, make_custom_object_classes_pydantic],
)
def test_ref_objects_across_artifacts_nocross(ref_tracking, get_custom_object_classes):
    CustomObjectA, CustomObjectB = get_custom_object_classes()

    # Case 1: No Cross Ref
    obj_a = CustomObjectA(inner_a=1)
    obj_b = CustomObjectB(inner_b=obj_a)
    saved_obj_b = weave.use(weave.save(obj_b))

    val = saved_obj_b.inner_b
    assert_local_ref(val, ["obj"], [OBJECT_ATTR_EDGE_NAME, "inner_b"])


@pytest.mark.parametrize(
    "get_custom_object_classes",
    [make_custom_object_classes_classic_type],
)
def test_ref_objects_across_artifacts_cross(ref_tracking, get_custom_object_classes):
    CustomObjectA, CustomObjectB = get_custom_object_classes()

    # Case 2: Cross Ref
    obj_a = CustomObjectA(inner_a=1)
    obj_a_ref = weave.use(weave.save(obj_a, "COB"))
    obj_b = CustomObjectB(inner_b=obj_a_ref)
    weave.types.type_of_with_refs(obj_b.inner_b)
    saved_obj_b = weave.use(weave.save(obj_b))

    val = saved_obj_b.inner_b
    # Notice that we have reset the ref structure here to the new artifact
    assert_local_ref(val, ["obj"], [])
