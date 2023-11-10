import pytest
import weave
from .. import artifact_local
from .. import artifact_fs
from .. import storage

from .. import ops_arrow as arrow


def test_artifact():
    data = arrow.to_arrow([{"a": 5}])
    data_ref = storage.save(data)
    assert data_ref.type == arrow.ArrowWeaveListType(
        object_type=weave.types.TypedDict(property_types={"a": weave.types.Int()})
    )
    assert data_ref.get() == data

    art = data_ref.artifact
    assert weave.type_of(art) == artifact_local.LocalArtifactType()
    art_ref = storage.save(art)
    # in the special case of saving an artifact, we have a ref to that artifact
    # instead of a new artifact
    assert art_ref.artifact == art and art_ref.path is None
    assert art_ref.get() == art
    assert art_ref.type == artifact_local.LocalArtifactType()

    art_dir = art.path_info("")
    assert weave.type_of(art_dir) == artifact_fs.FilesystemArtifactDirType()
    art_dir_ref = storage.save(art_dir)
    assert art_dir_ref.get() == art_dir
    assert art_dir_ref.type == artifact_fs.FilesystemArtifactDirType()

    art_dir_files = art_dir.files
    exp_art_file1_type = artifact_fs.FilesystemArtifactFileType(
        extension=weave.types.Const(weave.types.String(), "feather"),
        wbObjectType=weave.types.NoneType(),
    )
    assert weave.type_of(art_dir_files) == weave.types.TypedDict(
        {
            "obj.ArrowWeaveList.feather": artifact_fs.FilesystemArtifactFileType(
                extension=weave.types.Const(weave.types.String(), "feather"),
                wbObjectType=weave.types.NoneType(),
            ),
            "obj.ArrowWeaveList.type.json": artifact_fs.FilesystemArtifactFileType(
                extension=weave.types.Const(weave.types.String(), "json"),
                wbObjectType=weave.types.TypeType(attr_types={}),
            ),
            "obj.type.json": artifact_fs.FilesystemArtifactFileType(
                extension=weave.types.Const(weave.types.String(), "json"),
                wbObjectType=weave.types.TypeType(attr_types={}),
            ),
        }
    )
    assert len(art_dir.files) == 3

    art_file1 = art_dir_files["obj.ArrowWeaveList.feather"]
    assert art_file1 == artifact_fs.FilesystemArtifactFile(
        art, "obj.ArrowWeaveList.feather"
    )

    # Here we don't create a new object
    art_file1_ref = storage.save(art_file1)
    assert (
        art_file1_ref.artifact == art
        and art_file1_ref.path == "obj.ArrowWeaveList.feather"
    )
    assert art_file1_ref.type == exp_art_file1_type

    assert len(art_dir.dirs) == 0


def test_local_artifact_edits_correcty_set_previous_commit_pointers():
    target_artifact_name = "test_artifact"
    branch_name = "user-latest"
    source_branch_name = "user-latest"

    # Save local artifact
    edit_1 = storage._direct_save(
        obj=["initial_data"],
        name=target_artifact_name,
        branch_name=branch_name,
        source_branch_name=source_branch_name,
    )
    # Save a second version of the same local artifact
    edit_2 = storage._direct_save(
        obj=["test_data"],
        name=target_artifact_name,
        branch_name=branch_name,
        source_branch_name=source_branch_name,
    )
    assert edit_2.artifact.read_metadata()["previous_commit_uri"] == edit_1.artifact.uri


def test_local_artifact_name():
    with pytest.raises(ValueError):
        artifact_local.LocalArtifact("a/b")
    with pytest.raises(ValueError):
        artifact_local.LocalArtifact("a\\b")
    with pytest.raises(ValueError):
        artifact_local.LocalArtifact("a:b")
    with pytest.raises(ValueError):
        artifact_local.LocalArtifact("a..b")
