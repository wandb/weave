import wandb

import weave
from weave.legacy.weave import artifact_local, artifact_wandb
from weave.legacy.weave.wandb_interface.wandb_artifact_pusher import (
    write_artifact_to_wandb,
)


def without_keys(d, keys):
    return {k: v for k, v in d.items() if k not in keys}


def test_artifact_metadata(user_by_api_key_in_env):
    # Write some metadata to a local artifact
    local_art = artifact_local.LocalArtifact("test_artifact")
    local_art.set("obj", weave.types.Number(), 1)
    assert local_art.metadata.as_dict() == {}
    local_art.metadata["k_1"] = "v_1"
    local_art.metadata["k_2"] = "v_2"
    assert local_art.metadata.as_dict() == {"k_1": "v_1", "k_2": "v_2"}
    local_art.save()
    assert local_art.metadata.as_dict() == {
        "k_1": "v_1",
        "k_2": "v_2",
    }

    # Load the artifact and check the metadata
    local_art = artifact_local.LocalArtifact("test_artifact", "latest")
    assert local_art.metadata.as_dict() == {
        "k_1": "v_1",
        "k_2": "v_2",
    }

    # Overwrite one of the keys and add a new one
    local_art.metadata["k_1"] = "v_3"
    local_art.metadata["k_3"] = "v_4"
    assert local_art.metadata.as_dict() == {
        "k_1": "v_3",
        "k_2": "v_2",
        "k_3": "v_4",
    }
    local_art.save()
    assert local_art.metadata.as_dict() == {
        "k_1": "v_3",
        "k_2": "v_2",
        "k_3": "v_4",
    }

    # Verify that the metadata is correct
    local_art = artifact_local.LocalArtifact("test_artifact", "latest")
    assert local_art.metadata.as_dict() == {
        "k_1": "v_3",
        "k_2": "v_2",
        "k_3": "v_4",
    }

    # Push an artifact to wandb and verify that the metadata is correct
    remote_uri = weave.legacy.weave.ops.publish_artifact(
        weave.legacy.weave.ops.get(local_art.uri + "/obj"),
        "test_artifact",
        "test_project",
        None,
    )
    remote_ref = artifact_wandb.WandbArtifactRef.from_uri(
        artifact_wandb.WeaveWBArtifactURI.parse(remote_uri)
    )
    remote_art = remote_ref.artifact
    assert without_keys(remote_art.metadata.as_dict(), ["_weave_meta"]) == {
        "k_1": "v_3",
        "k_2": "v_2",
        "k_3": "v_4",
    }

    # Fork the artifact and sure the metadata persists
    forked_art = artifact_local.LocalArtifact.fork_from_uri(
        artifact_wandb.WeaveWBArtifactURI.parse(remote_uri)
    )
    assert without_keys(forked_art.metadata.as_dict(), ["_weave_meta"]) == {
        "k_1": "v_3",
        "k_2": "v_2",
        "k_3": "v_4",
    }
    forked_art.metadata["k_1"] = "v_5"
    forked_art.metadata["k_4"] = "v_6"
    assert without_keys(forked_art.metadata.as_dict(), ["_weave_meta"]) == {
        "k_1": "v_5",
        "k_2": "v_2",
        "k_3": "v_4",
        "k_4": "v_6",
    }
    forked_art.save()
    assert without_keys(forked_art.metadata.as_dict(), ["_weave_meta"]) == {
        "k_1": "v_5",
        "k_2": "v_2",
        "k_3": "v_4",
        "k_4": "v_6",
    }


def test_artifact_files_count(user_by_api_key_in_env):
    run = wandb.init(project="project_exists")
    artifact = wandb.Artifact("test", "datatest")
    table0 = wandb.Table(data=[[1, 2, 3]], columns=["a", "b", "c"])
    table1 = wandb.Table(data=[[1, 2, 3]], columns=["a", "b", "c"])
    table2 = wandb.Table(data=[[1, 2, 3]], columns=["a", "b", "c"])
    table3 = wandb.Table(data=[[1, 2, 3]], columns=["a", "b", "c"])
    artifact.add(table0, "table0")
    artifact.add(table1, "nest/table1")
    artifact.add(table2, "nest/nested/table2")
    artifact.add(table3, "nest/nested/nesteded/table3")
    run.log_artifact(artifact)
    run.finish()

    count_node = (
        weave.legacy.weave.ops.project(run.entity, run.project)
        .artifact("test")
        .membershipForAlias("v0")
        .artifactVersion()
        .files()
        .count()
    )
    assert weave.use(count_node) == 4
