from .. import artifact_local
from .. import artifact_util
from .. import ref_util


def test_laref_artifact_version():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "_obj")
    assert (
        str(ref)
        == "local-artifact://" + artifact_util.local_artifact_dir() + "/my-art/v19"
    )

    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "_obj"
    assert parsed_ref.extra == None

    assert ref.local_ref_str() == "_obj"
    assert ref_util.parse_local_ref_str("_obj") == ("_obj", None)


def test_laref_artifact_version_path():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "x.txt")
    assert (
        str(ref)
        == "local-artifact://"
        + artifact_util.local_artifact_dir()
        + "/my-art/v19?file=x.txt"
    )

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
    assert (
        str(ref)
        == "local-artifact://"
        + artifact_util.local_artifact_dir()
        + "/my-art/v19?extra=5&file=x.txt"
    )

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
    ref = artifact_local.LocalArtifactRef(art, "_obj", extra=["5"])
    assert (
        str(ref)
        == "local-artifact://"
        + artifact_util.local_artifact_dir()
        + "/my-art/v19?extra=5"
    )

    parsed_ref = artifact_local.LocalArtifactRef.from_str(str(ref))
    assert parsed_ref.artifact.name == art.name
    assert parsed_ref.artifact._version == art._version
    assert parsed_ref.path == "_obj"
    assert parsed_ref.extra == ["5"]

    assert ref.local_ref_str() == "_obj#5"
    assert ref_util.parse_local_ref_str("_obj#5") == (
        "_obj",
        ["5"],
    )


def test_laref_artifact_version_path_extra2():
    art = artifact_local.LocalArtifact("my-art", "v19")
    ref = artifact_local.LocalArtifactRef(art, "x.txt", extra=["5", "a"])
    assert (
        str(ref)
        == "local-artifact://"
        + artifact_util.local_artifact_dir()
        + "/my-art/v19?extra=5&extra=a&file=x.txt"
    )

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
