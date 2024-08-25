import typing

import pytest

import weave
from weave.legacy.weave import panels, storage
from weave.legacy.weave.artifact_fs import BranchPointType, FilesystemArtifactRef
from weave.legacy.weave.artifact_local import (
    LocalArtifact,
    LocalArtifactRef,
    WeaveLocalArtifactURI,
)
from weave.legacy.weave.artifact_wandb import (
    WandbArtifact,
    WandbArtifactRef,
    WeaveWBArtifactURI,
    likely_commit_hash,
)
from weave.legacy.weave.uris import WeaveURI


def test_publish_values(user_by_api_key_in_env):
    data = ["a", "b", "c"]
    ref = storage.publish(data, "weave/list")
    assert ref.get() == data


def test_publish_panel(user_by_api_key_in_env):
    from weave.legacy.weave import panel_util

    table_obj = panels.Table(
        panel_util.make_node(
            [
                {"a": 1, "b": 2, "c": 3},
                {"a": 4, "b": 5, "c": 6},
                {"a": 7, "b": 8, "c": 9},
            ]
        ),
        columns=[
            lambda row: row["a"],
            lambda row: row["b"],
            lambda row: row["c"],
        ],
    )
    ref = storage.publish(table_obj, "weave/table")
    assert isinstance(ref, WandbArtifactRef)


def test_publish_table(user_by_api_key_in_env):
    table_obj = panels.Table(
        weave.save(
            [
                {"a": 1, "b": 2, "c": 3},
                {"a": 4, "b": 5, "c": 6},
                {"a": 7, "b": 8, "c": 9},
            ]
        ),
        columns=[
            lambda row: row["a"],
            lambda row: row["b"],
            lambda row: row["c"],
        ],
    )
    ref = storage.publish(table_obj, "weave/table")
    assert (
        ref.get().input_node.from_op.inputs["uri"].val.startswith("wandb-artifact://")
    )


def test_publish_group(user_by_api_key_in_env):
    local_data = weave.save(
        [
            {"a": 1, "b": 2, "c": 3},
            {"a": 4, "b": 5, "c": 6},
            {"a": 7, "b": 8, "c": 9},
        ]
    )

    group = panels.Group(
        items={
            "table": panels.Table(
                local_data,
                columns=[
                    lambda row: row["a"],
                    lambda row: row["b"] * 2,
                ],
            ),
            "plot": lambda table: panels.Plot(
                table.all_rows(),
                x=lambda row: row["c_0"],
                y=lambda row: row["c_1"],
            ),
        }
    )

    res = storage.publish(group, "weave/group")


"""
TODO: These tests were written in prep for the launch and need to be cleaned up
and made more maintainable/understandable. This is a followup action on Tim.

The following tests exercise the save & publish flows. There are 2 dimensions to test:

* The `Location` of the data.
* The `Action` to take on the data.

There are 6 possible `Location` types:

1. Remote with commit hash (eg. `wandb-artifact://ENTITY/PROJECT/NAME:HASH`)
2. Remote with branch (eg. `wandb-artifact://ENTITY/PROJECT/NAME:BRANCH`)
3-4. Local with commit hash (eg. `wandb-artifact://ENTITY/PROJECT/NAME:HASH`). Variants:
    a. No branchpoint
    b. With branchpoint
5-6. Local with branch (eg. `wandb-artifact://ENTITY/PROJECT/NAME:BRANCH`). Variants:
    a. No branchpoint
    b. With branchpoint

There are 3 actions:

1. `Persist`: Directly persist data (eq. save or publish directly)
2. `Mutate`: Generate new version via Mutation
3. `Merge`: Apply changes to branchpoint (only applicable to locations with branchpoint)
   * The branchpoint URI can be any of the 6 location types above.

In summary, there will be 22 tests:

* 6 `Persist` tests
* 6 `Mutate` tests
* 2 * 6 `Merge` tests (2 types of branchpoints, and 6 branch location types.)
   * -2 cases that are not possible
"""


# Persist tests
def test_persist_to_remote_with_commit_hash(user_by_api_key_in_env):
    data = ["test_data"]
    target_entity = user_by_api_key_in_env.username
    target_project_name = "test_project"
    target_artifact_name = "test_artifact"
    expected_commit_hash = "74d5ba98aca469b59e18"
    branch_name = None

    p_ref = storage._direct_publish(
        obj=data,
        name=target_artifact_name,
        wb_project_name=target_project_name,
        wb_entity_name=target_entity,
        branch_name=branch_name,
    )

    _perform_post_persist_assertions(
        is_local=False,
        data=data,
        p_ref=p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=expected_commit_hash,
        target_entity=target_entity,
        target_project_name=target_project_name,
        branch_name=branch_name,
    )


def test_persist_to_remote_with_branch(user_by_api_key_in_env):
    data = ["test_data"]
    target_entity = user_by_api_key_in_env.username
    target_project_name = "test_project"
    target_artifact_name = "test_artifact"
    expected_commit_hash = "74d5ba98aca469b59e18"
    branch_name = "test_branch"

    p_ref = storage._direct_publish(
        obj=data,
        name=target_artifact_name,
        wb_project_name=target_project_name,
        wb_entity_name=target_entity,
        branch_name=branch_name,
    )

    _perform_post_persist_assertions(
        is_local=False,
        data=data,
        p_ref=p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=expected_commit_hash,
        target_entity=target_entity,
        target_project_name=target_project_name,
        branch_name=branch_name,
    )


def test_persist_to_local_with_commit_hash(user_by_api_key_in_env):
    data = ["test_data"]
    target_artifact_name = "test_artifact"
    expected_commit_hash = "b11179315e19b4207282"
    branch_name = None

    p_ref = storage.direct_save(
        obj=data,
        name=target_artifact_name,
        branch_name=branch_name,
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=data,
        p_ref=p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=expected_commit_hash,
        branch_name=branch_name,
    )


# Skipping as this one does not make logical sense.
# def test_persist_to_local_with_commit_hash_and_branchpoint(user_by_api_key_in_env):
#     pass


def test_persist_to_local_with_branch(user_by_api_key_in_env):
    data = ["test_data"]
    target_artifact_name = "test_artifact"
    expected_commit_hash = "b11179315e19b4207282"
    branch_name = "my_branch"

    p_ref = storage.direct_save(
        obj=data,
        name=target_artifact_name,
        branch_name=branch_name,
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=data,
        p_ref=p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=expected_commit_hash,
        branch_name=branch_name,
    )


def test_persist_to_local_with_branch_and_branchpoint(user_by_api_key_in_env):
    data = ["test_data"]
    target_artifact_name = "test_artifact"
    expected_commit_hash = "b11179315e19b4207282"
    branch_name = "my_branch"

    source_branch_name = "initial_branch"
    source_commit_hash = "741eb73e40d3b38b046b"

    # First, save a local artifact with a branch
    p_ref = storage.direct_save(
        obj=["initial_data"],
        name=target_artifact_name,
        branch_name=source_branch_name,
    )

    # Then, save a new local artifact with a branchpoint
    new_p_ref = storage.direct_save(
        obj=data,
        name=target_artifact_name,
        branch_name=branch_name,
        source_branch_name=source_branch_name,
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=expected_commit_hash,
        branch_name=branch_name,
        expected_branchpoint=BranchPointType(
            commit=source_commit_hash,
            n_commits=1,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        ),
    )


def _perform_post_persist_assertions(
    is_local: bool,
    data: typing.Any,
    p_ref: FilesystemArtifactRef,
    target_artifact_name: str,
    expected_commit_hash: str,
    target_entity: typing.Optional[str] = None,
    target_project_name: typing.Optional[str] = None,
    branch_name: typing.Optional[str] = None,
    expected_branchpoint: typing.Optional[BranchPointType] = None,
):
    p_uri: WeaveURI
    p_art: typing.Union[WandbArtifact, LocalArtifact]

    if is_local:
        assert isinstance(p_ref, LocalArtifactRef)
        p_art = p_ref.artifact
        assert isinstance(p_art, LocalArtifact)
        p_uri = p_art.uri_obj
        assert isinstance(p_uri, WeaveLocalArtifactURI)
        assert target_entity is None
        assert target_project_name is None
        expected_uri_with_hash = (
            f"local-artifact:///{target_artifact_name}:{expected_commit_hash}/obj"
        )
        expected_uri_with_branch = None
        if branch_name:
            expected_uri_with_branch = (
                f"local-artifact:///{target_artifact_name}:{branch_name}/obj"
            )
    else:
        assert isinstance(p_ref, WandbArtifactRef)
        p_art = p_ref.artifact
        assert isinstance(p_art, WandbArtifact)
        p_uri = p_art.uri_obj
        assert isinstance(p_uri, WeaveWBArtifactURI)
        assert target_entity is not None
        assert target_project_name is not None
        expected_uri_with_hash = f"wandb-artifact:///{target_entity}/{target_project_name}/{target_artifact_name}:{expected_commit_hash}/obj"
        expected_uri_with_branch = None
        if branch_name:
            expected_uri_with_branch = f"wandb-artifact:///{target_entity}/{target_project_name}/{target_artifact_name}:{branch_name}/obj"

    # Data Assertions
    get_op = weave.legacy.weave.ops.get(expected_uri_with_hash)
    get_res = weave.use(get_op)
    assert p_ref.obj == get_res == data
    # Only check branch if expected_uri_with_branch is not None
    if expected_uri_with_branch:
        get_op = weave.legacy.weave.ops.get(expected_uri_with_branch)
        get_res = weave.use(get_op)
        assert get_res == data

    # Identity Assertions (entity, project, name, version)
    if not is_local:
        assert isinstance(p_uri, WeaveWBArtifactURI)
        assert p_uri.entity_name == target_entity
        assert p_uri.project_name == target_project_name
    assert p_ref.name == p_art.name == p_uri.name == target_artifact_name
    assert likely_commit_hash(expected_commit_hash) and (
        p_ref.version == p_art.version == p_uri.version == expected_commit_hash
    )
    if not is_local:
        assert isinstance(p_art, WandbArtifact)
        assert p_art.commit_hash == expected_commit_hash
    else:
        assert p_art.version == expected_commit_hash

    assert p_ref.branch == p_art.branch
    assert p_art.branch == branch_name

    # Branchpoint Assertions
    assert p_ref.branch_point == p_art.branch_point == expected_branchpoint

    # URI Assertions
    assert p_ref.initial_uri == expected_uri_with_branch or expected_uri_with_hash
    assert p_ref.uri == expected_uri_with_hash
    assert p_ref.branch_uri == expected_uri_with_branch or expected_uri_with_hash


# Mutate tests
def test_mutate_remote_with_commit_hash(user_by_api_key_in_env):
    data = ["test_data"]
    target_entity = user_by_api_key_in_env.username
    target_project_name = "test_project"
    target_artifact_name = "test_artifact"
    expected_commit_hash = "74d5ba98aca469b59e18"
    branch_name = None

    new_data = ["test_data_2"]
    new_commit_hash = "61f78c8877df22942d23"

    p_ref = storage._direct_publish(
        obj=data,
        name=target_artifact_name,
        wb_project_name=target_project_name,
        wb_entity_name=target_entity,
        branch_name=branch_name,
    )

    assert p_ref.version == expected_commit_hash

    obj = weave.legacy.weave.ops.get(p_ref.uri)[0]
    obj.set(new_data[0])
    new_branch_name = f"user-{p_ref.version}"
    new_uri = f"local-artifact:///{target_artifact_name}:{new_branch_name}/obj"
    new_p_ref = LocalArtifactRef.from_str(new_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=new_data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=new_commit_hash,
        branch_name=new_branch_name,
        expected_branchpoint=BranchPointType(
            commit=expected_commit_hash,
            n_commits=1,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        ),
    )


def test_mutate_remote_with_branch(user_by_api_key_in_env):
    data = ["test_data"]
    target_entity = user_by_api_key_in_env.username
    target_project_name = "test_project"
    target_artifact_name = "test_artifact"
    expected_commit_hash = "74d5ba98aca469b59e18"
    branch_name = "remote_branch"

    new_data = ["test_data_2"]
    new_commit_hash = "61f78c8877df22942d23"

    p_ref = storage._direct_publish(
        obj=data,
        name=target_artifact_name,
        wb_project_name=target_project_name,
        wb_entity_name=target_entity,
        branch_name=branch_name,
    )

    assert p_ref.version == expected_commit_hash
    assert branch_name in p_ref.branch_uri

    obj = weave.legacy.weave.ops.get(p_ref.branch_uri)[0]
    obj.set(new_data[0])
    new_branch_name = f"user-{branch_name}"
    new_p_ref = LocalArtifactRef.from_str(
        f"local-artifact:///{target_artifact_name}:{new_branch_name}/obj"
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=new_data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=new_commit_hash,
        branch_name=new_branch_name,
        expected_branchpoint=BranchPointType(
            commit=expected_commit_hash,
            n_commits=1,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        ),
    )


def test_mutate_local_with_commit_hash(user_by_api_key_in_env, new_branch_name=None):
    data = ["test_data"]
    target_artifact_name = "test_artifact"
    expected_commit_hash = "b11179315e19b4207282"
    branch_name = None

    new_data = ["test_data_2"]
    new_commit_hash = "61f78c8877df22942d23"

    p_ref = storage.direct_save(
        obj=data,
        name=target_artifact_name,
        branch_name=branch_name,
    )

    assert p_ref.version == expected_commit_hash

    obj = weave.legacy.weave.ops.get(p_ref.uri)[0]
    if new_branch_name == None:
        obj.set(new_data[0])
        new_branch_name = new_commit_hash
        expected_branchpoint = None
    else:
        obj.set(new_data[0], root_args={"branch": new_branch_name})
        branch_name = new_branch_name
        expected_branchpoint = BranchPointType(
            commit=expected_commit_hash,
            n_commits=1,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        )
    new_p_ref = LocalArtifactRef.from_str(
        f"local-artifact:///{target_artifact_name}:{new_branch_name}/obj"
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=new_data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=new_commit_hash,
        branch_name=branch_name,
        expected_branchpoint=expected_branchpoint,
    )


def test_mutate_local_with_commit_hash_and_branchpoint(
    user_by_api_key_in_env, new_branch_name=None
):
    data = ["test_data"]
    target_entity = user_by_api_key_in_env.username
    target_project_name = "test_project"
    target_artifact_name = "test_artifact"
    expected_commit_hash = "74d5ba98aca469b59e18"
    branch_name = "remote_branch"

    new_data = ["test_data_2"]
    new_commit_hash = "61f78c8877df22942d23"

    p_ref = storage._direct_publish(
        obj=data,
        name=target_artifact_name,
        wb_project_name=target_project_name,
        wb_entity_name=target_entity,
        branch_name=branch_name,
    )

    assert p_ref.version == expected_commit_hash
    assert branch_name in p_ref.branch_uri

    obj = weave.legacy.weave.ops.get(p_ref.branch_uri)[0]
    obj.set("PLACEHOLDER")
    mod_ref = LocalArtifactRef.from_uri(
        WeaveLocalArtifactURI.parse(
            f"local-artifact:///{target_artifact_name}:user-{branch_name}/obj"
        )
    )
    obj = weave.legacy.weave.ops.get(mod_ref.branch_uri)[0]
    if new_branch_name == None:
        obj.set(new_data[0])
        branch_name = None
        new_branch_name = new_commit_hash
        expected_branchpoint = BranchPointType(
            commit=expected_commit_hash,
            n_commits=2,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        )
    else:
        obj.set(new_data[0], root_args={"branch": new_branch_name})
        branch_name = new_branch_name
        expected_branchpoint = BranchPointType(
            commit="0dc63f69254034abd6f9",
            n_commits=1,
            original_uri=str(mod_ref.branch_uri).replace("/obj", ""),
        )

    new_p_ref = LocalArtifactRef.from_str(
        f"local-artifact:///{target_artifact_name}:{new_branch_name}/obj"
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=new_data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=new_commit_hash,
        branch_name=branch_name,
        expected_branchpoint=expected_branchpoint,
    )


def test_mutate_local_with_branch(user_by_api_key_in_env, new_branch_name=None):
    data = ["test_data"]
    target_artifact_name = "test_artifact"
    expected_commit_hash = "b11179315e19b4207282"
    branch_name = "my_branch"

    new_data = ["test_data_2"]
    new_commit_hash = "61f78c8877df22942d23"

    p_ref = storage.direct_save(
        obj=data,
        name=target_artifact_name,
        branch_name=branch_name,
    )

    assert p_ref.version == expected_commit_hash

    obj = weave.legacy.weave.ops.get(p_ref.branch_uri)[0]
    if new_branch_name == None:
        obj.set(new_data[0])
        new_branch_name = new_commit_hash
        expected_branchpoint = None
    else:
        obj.set(new_data[0], root_args={"branch": new_branch_name})
        branch_name = new_branch_name
        expected_branchpoint = BranchPointType(
            commit=expected_commit_hash,
            n_commits=1,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        )
    new_branch_name = branch_name
    new_p_ref = LocalArtifactRef.from_str(
        f"local-artifact:///{target_artifact_name}:{new_branch_name}/obj"
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=new_data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=new_commit_hash,
        branch_name=new_branch_name,
        expected_branchpoint=expected_branchpoint,
    )


def test_mutate_local_with_branch_and_branchpoint(user_by_api_key_in_env):
    data = ["test_data"]
    target_entity = user_by_api_key_in_env.username
    target_project_name = "test_project"
    target_artifact_name = "test_artifact"
    expected_commit_hash = "74d5ba98aca469b59e18"
    branch_name = "remote_branch"

    new_data = ["test_data_2"]
    new_commit_hash = "61f78c8877df22942d23"

    p_ref = storage._direct_publish(
        obj=data,
        name=target_artifact_name,
        wb_project_name=target_project_name,
        wb_entity_name=target_entity,
        branch_name=branch_name,
    )

    assert p_ref.version == expected_commit_hash
    assert branch_name in p_ref.branch_uri

    obj = weave.legacy.weave.ops.get(p_ref.branch_uri)[0]
    obj.set("PLACEHOLDER")
    obj = weave.legacy.weave.ops.get(
        f"local-artifact:///{target_artifact_name}:user-{branch_name}/obj"
    )[0]
    obj.set(new_data[0])
    new_p_ref = LocalArtifactRef.from_str(
        f"local-artifact:///{target_artifact_name}:user-{branch_name}/obj"
    )

    _perform_post_persist_assertions(
        is_local=True,
        data=new_data,
        p_ref=new_p_ref,
        target_artifact_name=target_artifact_name,
        expected_commit_hash=new_commit_hash,
        branch_name=f"user-{branch_name}",
        expected_branchpoint=BranchPointType(
            commit=expected_commit_hash,
            n_commits=2,
            original_uri=str(p_ref.branch_uri).replace("/obj", ""),
        ),
    )


# Merge Tests


def test_merge_from_local_with_commit_hash_onto_remote_with_commit_hash(
    user_by_api_key_in_env,
):
    test_mutate_remote_with_commit_hash(user_by_api_key_in_env)

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:61f78c8877df22942d23/obj")
    )

    assert merged_uri.startswith("wandb-artifact://")
    assert "5a61da7b34feb72c2af8" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=False,
        target_entity=user_by_api_key_in_env.username,
        target_project_name="test_project",
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="5a61da7b34feb72c2af8",
        branch_name=None,
    )


def test_merge_from_local_with_commit_hash_onto_remote_with_branch(
    user_by_api_key_in_env,
):
    test_mutate_remote_with_branch(user_by_api_key_in_env)

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:61f78c8877df22942d23/obj")
    )

    assert merged_uri.startswith("wandb-artifact://")
    assert "remote_branch" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=False,
        target_entity=user_by_api_key_in_env.username,
        target_project_name="test_project",
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="5a61da7b34feb72c2af8",
        branch_name="remote_branch",
    )


def test_merge_from_local_with_commit_hash_onto_local_with_commit_hash(
    user_by_api_key_in_env,
):
    test_mutate_local_with_commit_hash(user_by_api_key_in_env, "new_branch_name")

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:61f78c8877df22942d23/obj")
    )

    assert merged_uri.startswith("local-artifact://")
    assert "61f78c8877df22942d23" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="61f78c8877df22942d23",
        branch_name=None,
    )


# def test_merge_from_local_with_commit_hash_onto_local_with_commit_hash_and_branchpoint(
#     user_by_api_key_in_env,
# ):
#     # Leaving the test stub here for completeness of the permutations, but I am
#     # not convinced it is even possible to get into this state.
#     pass


def test_merge_from_local_with_commit_hash_onto_local_with_branch(
    user_by_api_key_in_env,
):
    test_mutate_local_with_branch(user_by_api_key_in_env, "new_branch_name")

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:61f78c8877df22942d23/obj")
    )

    assert merged_uri.startswith("local-artifact://")
    assert "my_branch" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="61f78c8877df22942d23",
        branch_name="my_branch",
    )


def test_merge_from_local_with_commit_hash_onto_local_with_branch_and_branchpoint(
    user_by_api_key_in_env,
):
    test_mutate_local_with_commit_hash_and_branchpoint(
        user_by_api_key_in_env, "new_branch_name"
    )

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:61f78c8877df22942d23/obj")
    )

    assert merged_uri.startswith("local-artifact://")
    assert "remote_branch" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="61f78c8877df22942d23",
        branch_name="user-remote_branch",
        expected_branchpoint=BranchPointType(
            n_commits=2,
            commit="74d5ba98aca469b59e18",
            original_uri=f"wandb-artifact:///{user_by_api_key_in_env.username}/test_project/test_artifact:remote_branch",
        ),
    )

    merged_uri_2 = weave.legacy.weave.ops.merge_artifact(weave.legacy.weave.ops.get(merged_uri))
    new_p_ref_2 = WandbArtifactRef.from_str(merged_uri_2)

    assert merged_uri_2.startswith("wandb-artifact://")
    assert "remote_branch" in merged_uri_2

    new_p_ref = WandbArtifactRef.from_str(merged_uri_2)

    _perform_post_persist_assertions(
        is_local=False,
        data=["test_data_2"],
        p_ref=new_p_ref_2,
        target_artifact_name="test_artifact",
        expected_commit_hash="5a61da7b34feb72c2af8",
        branch_name="remote_branch",
        target_entity=user_by_api_key_in_env.username,
        target_project_name="test_project",
    )


# Merge Tests


def test_merge_from_local_with_branch_onto_remote_with_commit_hash(
    user_by_api_key_in_env,
):
    test_mutate_remote_with_commit_hash(user_by_api_key_in_env)

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get(
            "local-artifact:///test_artifact:user-74d5ba98aca469b59e18/obj"
        )
    )

    assert merged_uri.startswith("wandb-artifact://")
    assert "5a61da7b34feb72c2af8" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=False,
        target_entity=user_by_api_key_in_env.username,
        target_project_name="test_project",
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="5a61da7b34feb72c2af8",
        branch_name=None,
    )


def test_merge_from_local_with_branch_onto_remote_with_branch(user_by_api_key_in_env):
    test_mutate_remote_with_branch(user_by_api_key_in_env)

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:user-remote_branch/obj")
    )

    assert merged_uri.startswith("wandb-artifact://")
    assert "remote_branch" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=False,
        target_entity=user_by_api_key_in_env.username,
        target_project_name="test_project",
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="5a61da7b34feb72c2af8",
        branch_name="remote_branch",
    )


def test_merge_from_local_with_branch_onto_local_with_commit_hash(
    user_by_api_key_in_env,
):
    test_mutate_local_with_commit_hash(user_by_api_key_in_env, "new_branch_name")

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:new_branch_name/obj")
    )

    assert merged_uri.startswith("local-artifact://")
    assert "61f78c8877df22942d23" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="61f78c8877df22942d23",
        branch_name=None,
    )


# def test_merge_from_local_with_branch_onto_local_with_commit_hash_and_branchpoint(
#     user_by_api_key_in_env,
# ):
#     # Leaving the test stub here for completeness of the permutations, but I am
#     # not convinced it is even possible to get into this state.
#     pass


def test_merge_from_local_with_branch_onto_local_with_branch(user_by_api_key_in_env):
    test_mutate_local_with_branch(user_by_api_key_in_env, "new_branch_name")

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:new_branch_name/obj")
    )

    assert merged_uri.startswith("local-artifact://")
    assert "my_branch" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="61f78c8877df22942d23",
        branch_name="my_branch",
    )


def test_merge_from_local_with_branch_onto_local_with_branch_and_branchpoint(
    user_by_api_key_in_env,
):
    test_mutate_local_with_commit_hash_and_branchpoint(
        user_by_api_key_in_env, "new_branch_name"
    )

    merged_uri = weave.legacy.weave.ops.merge_artifact(
        weave.legacy.weave.ops.get("local-artifact:///test_artifact:new_branch_name/obj")
    )

    assert merged_uri.startswith("local-artifact://")
    assert "remote_branch" in merged_uri

    new_p_ref = WandbArtifactRef.from_str(merged_uri)

    _perform_post_persist_assertions(
        is_local=True,
        data=["test_data_2"],
        p_ref=new_p_ref,
        target_artifact_name="test_artifact",
        expected_commit_hash="61f78c8877df22942d23",
        branch_name="user-remote_branch",
        expected_branchpoint=BranchPointType(
            n_commits=2,
            commit="74d5ba98aca469b59e18",
            original_uri=f"wandb-artifact:///{user_by_api_key_in_env.username}/test_project/test_artifact:remote_branch",
        ),
    )

    merged_uri_2 = weave.legacy.weave.ops.merge_artifact(weave.legacy.weave.ops.get(merged_uri))
    new_p_ref_2 = WandbArtifactRef.from_str(merged_uri_2)

    assert merged_uri_2.startswith("wandb-artifact://")
    assert "remote_branch" in merged_uri_2

    new_p_ref = WandbArtifactRef.from_str(merged_uri_2)

    _perform_post_persist_assertions(
        is_local=False,
        data=["test_data_2"],
        p_ref=new_p_ref_2,
        target_artifact_name="test_artifact",
        expected_commit_hash="5a61da7b34feb72c2af8",
        branch_name="remote_branch",
        target_entity=user_by_api_key_in_env.username,
        target_project_name="test_project",
    )


## Custom Flow


def test_publish_saved_node(user_by_api_key_in_env):
    data = ["test_publish_saved_node"]
    saved = weave.save(data)
    assert saved.from_op.inputs["uri"].val.startswith("local-artifact://")
    assert weave.use(saved) == data

    published_art_uri = weave.legacy.weave.ops.publish_artifact(saved, "my_list", None, None)
    assert published_art_uri.startswith("wandb-artifact://")
    assert weave.use(weave.get(published_art_uri)) == data


def _uri_is_local(uri: str) -> bool:
    return uri.startswith("local-artifact://")


def _uri_is_remote(uri: str) -> bool:
    return uri.startswith("wandb-artifact://")


def _get_uri_version(uri: str) -> str:
    return uri.split(":")[-1].split("/")[0]


def _replace_uri_version(uri: str, new_version: str) -> str:
    return uri.replace(_get_uri_version(uri), new_version)


def _get_uri_from_get_node(node: weave.legacy.weave.graph.Node) -> str:
    return node.from_op.inputs["uri"].val  # type: ignore


def test_end_to_end_save_and_publish_flow(user_by_api_key_in_env):
    # Step 1: Save some data locally.
    data = ["data_a"]
    saved_node = weave.save(data)
    saved_uri = _get_uri_from_get_node(saved_node)
    saved_version = _get_uri_version(saved_uri)
    assert _uri_is_local(saved_uri)
    assert weave.use(saved_node) == data

    # Step 2: Make a branching mutation.
    weave.legacy.weave.ops.set(
        saved_node[0],
        "test_publish_saved_node_execution_2",
        root_args={"branch": "my-branch"},
    )
    branched_data = ["test_publish_saved_node_execution_2"]
    branched_uri = saved_uri.replace(saved_version, "my-branch")
    branched_node = weave.legacy.weave.ops.get(branched_uri)
    assert weave.use(branched_node) == branched_data

    # Step 3: Merge the change back into the main branch.
    merged_uri = weave.legacy.weave.ops.merge_artifact(branched_node)
    assert merged_uri.startswith("local-artifact://")
    assert merged_uri != saved_uri != branched_uri
    merged_node = weave.legacy.weave.ops.get(merged_uri)
    assert weave.use(merged_node) == branched_data

    # Step 4: Publish the new version remotely
    published_uri = weave.legacy.weave.ops.publish_artifact(
        merged_node, "my_list", None, None
    )
    assert published_uri.startswith("wandb-artifact://")
    assert weave.use(weave.get(published_uri)) == branched_data

    # Step 5: Modify the remote version
    weave.legacy.weave.ops.set(
        weave.legacy.weave.ops.get(published_uri)[0],
        "test_publish_saved_node_execution_3",
        root_args={"branch": "my-branch-2"},
    )
    published_branched_data = ["test_publish_saved_node_execution_3"]
    published_branched_uri = "local-artifact:///my_list:my-branch-2/obj"
    published_branched_node = weave.legacy.weave.ops.get(published_branched_uri)
    assert weave.use(published_branched_node) == published_branched_data

    # Step 6: Merge the remote change back into the main branch.
    published_merged_uri = weave.legacy.weave.ops.merge_artifact(published_branched_node)
    assert published_merged_uri.startswith("wandb-artifact://")
    assert published_merged_uri != published_uri
    published_merged_node = weave.legacy.weave.ops.get(published_merged_uri)
    assert weave.use(published_merged_node) == published_branched_data
