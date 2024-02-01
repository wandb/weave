import weave
from .. import artifact_local
from .. import ref_util
from .. import storage
from .. import ops_arrow as arrow


def test_laref_artifact_version_1():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "obj")
    assert str(ref) == "local-artifact:///my-art:v19/obj"

    print("STR", str(ref))
    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "obj"
    assert parsed_ref.extra == None

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
    assert parsed_ref.extra == None

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


def test_ref_extra_dict(ref_tracking):
    obj = {"a": 1}
    saved_obj = weave.use(weave.save(obj))

    assert saved_obj == obj
    assert_local_ref(saved_obj, ["obj"], [])
    assert storage.get(saved_obj._ref.uri) == obj

    val = saved_obj["a"]
    assert val == 1
    assert_local_ref(val, ["obj"], ["key", "a"])
    assert storage.get(val._ref.uri) == 1


def test_ref_extra_list(ref_tracking):
    obj = [1]
    saved_obj = weave.use(weave.save(obj))

    assert saved_obj == obj
    assert_local_ref(saved_obj, ["obj"], [])
    assert storage.get(saved_obj._ref.uri) == obj

    val = saved_obj[0]
    assert val == 1
    assert_local_ref(val, ["obj"], ["idx", "0"])
    assert storage.get(val._ref.uri) == 1


def test_ref_extra_object(ref_tracking):
    @weave.type()
    class CustomObject:
        inner_a: int

    obj = CustomObject(inner_a=1)
    saved_obj = weave.use(weave.save(obj))

    assert_local_ref(saved_obj, ["obj"], [])

    val = saved_obj.inner_a
    assert val == 1
    assert_local_ref(val, ["obj"], ["attr", "inner_a"])
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
    assert_local_ref(val, ["obj"], ["idx", "0"])
    assert storage.get(val._ref.uri) == {"a": 1}

    val = saved_obj.column("a")
    assert val.to_pylist_notags() == [1, 2]
    assert_local_ref(val, ["obj"], ["col", "a"])
    assert storage.get(val._ref.uri).to_pylist_notags() == [1, 2]


def test_ref_extra_table_very_nested(ref_tracking):
    @weave.type()
    class CustomObject:
        inner_a: int

    arrow_raw = arrow.to_arrow(
        [
            {
                "a": arrow.to_arrow(
                    [
                        CustomObject(inner_a=1),
                    ]
                )
            },
        ]
    )

    saved_obj = weave.use(weave.save(arrow_raw))

    assert saved_obj.to_pylist_notags() == arrow_raw.to_pylist_notags()

    val = saved_obj[0]["a"][0].inner_a
    assert val == 1
    assert_local_ref(
        saved_obj[0]["a"][0].inner_a,
        ["obj"],
        ["idx", "0", "key", "a", "idx", "0", "attr", "inner_a"],
    )
    assert storage.get(val._ref.uri) == 1
