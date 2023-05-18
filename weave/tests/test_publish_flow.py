import weave


def test_publish_values(user_by_api_key_in_env):
    data = ["a", "b", "c"]
    res = weave.publish(data, "weave/list")
    assert weave.use(res) == data


def test_publish_panel(user_by_api_key_in_env):
    table_obj = weave.panels.Table(
        weave.make_node(
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
    res = weave.publish(table_obj, "weave/table")
    assert isinstance(res, weave.graph.Node)


def test_publish_table(user_by_api_key_in_env):
    table_obj = weave.panels.Table(
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
    res = weave.publish(table_obj)
    assert res.val.input_node.from_op.inputs["uri"].val.startswith("wandb-artifact://")


def test_publish_group(user_by_api_key_in_env):
    local_data = weave.save(
        [
            {"a": 1, "b": 2, "c": 3},
            {"a": 4, "b": 5, "c": 6},
            {"a": 7, "b": 8, "c": 9},
        ]
    )

    group = weave.panels.Group(
        items={
            "table": weave.panels.Table(
                local_data,
                columns=[
                    lambda row: row["a"],
                    lambda row: row["b"] * 2,
                ],
            ),
            "plot": lambda table: weave.panels.Plot(
                table.all_rows(),
                x=lambda row: row["c_0"],
                y=lambda row: row["c_1"],
            ),
        }
    )

    res = weave.publish(group)


def test_publish_saved_node(user_by_api_key_in_env):
    data = ["test_publish_saved_node"]
    saved = weave.save(data)
    assert saved.from_op.inputs["uri"].val.startswith("local-artifact://")
    assert weave.use(saved) == data

    published = weave.ops.publish_artifact(saved, "weave_ops", "my_list")
    assert published.from_op.inputs["uri"].val.startswith("wandb-artifact://")
    assert weave.use(published) == data


def test_publish_saved_node_execution(user_by_api_key_in_env):
    data = ["test_publish_saved_node_execution"]
    saved = weave.save(data)
    assert saved.from_op.inputs["uri"].val.startswith("local-artifact://")
    assert weave.use(saved) == data

    published = weave.ops.publish_artifact.lazy_call(
        weave.ops.get(saved.from_op.inputs["uri"]), "weave_ops", "my_list"
    )
    after_publish = weave.use(published)
    assert after_publish.from_op.inputs["uri"].val.startswith("wandb-artifact://")
    assert weave.use(after_publish) == data


def test_end_to_end_save_and_publish_flow(user_by_api_key_in_env):
    # Step 1: Save some data locally.
    data = ["test_publish_saved_node_execution"]
    saved_node = weave.save(data)
    saved_uri = saved_node.from_op.inputs["uri"].val
    assert saved_uri.startswith("local-artifact://")
    assert weave.use(saved_node) == data
    saved_version = saved_uri.split("local-artifact:///list:", 1)[1].split("/", 1)[0]

    # Step 2: Make a branching mutation.
    branched_uri = weave.ops.set(
        saved_node[0],
        "test_publish_saved_node_execution_2",
        root_args={"branch": "my-branch"},
    )
    branched_data = ["test_publish_saved_node_execution_2"]
    assert branched_uri == saved_uri.replace(saved_version, "my-branch")
    branched_node = weave.ops.get(branched_uri)
    assert weave.use(branched_node) == branched_data

    # Step 3: Merge the change back into the main branch.
    merged_uri = weave.ops.merge(branched_node)
    assert merged_uri.startswith("local-artifact://")
    assert merged_uri != saved_uri != branched_uri
    merged_node = weave.ops.get(merged_uri)
    assert weave.use(merged_node) == branched_data

    # Step 4: Publish the new version remotely
    published_node = weave.ops.publish_artifact(merged_node, "weave_ops", "my_list")
    published_uri = published_node.from_op.inputs["uri"].val
    assert published_uri.startswith("wandb-artifact://")
    assert weave.use(published_node) == branched_data

    # Step 5: Modify the remote version
    published_branched_uri = weave.ops.set(
        published_node[0],
        "test_publish_saved_node_execution_3",
        root_args={"branch": "my-branch-2"},
    )
    published_branched_data = ["test_publish_saved_node_execution_3"]
    assert published_branched_uri == "local-artifact:///my_list:my-branch-2/obj"
    published_branched_node = weave.ops.get(published_branched_uri)
    assert weave.use(published_branched_node) == published_branched_data

    # Step 6: Merge the remote change back into the main branch.
    published_merged_uri = weave.ops.merge(published_branched_node)
    assert published_merged_uri.startswith("wandb-artifact://")
    assert published_merged_uri != published_uri
    published_merged_node = weave.ops.get(published_merged_uri)
    assert weave.use(published_merged_node) == published_branched_data


def test_publish_with_branch(user_by_api_key_in_env):
    data = ["test_publish_saved_node_execution"]
    saved_node = weave.save(data, "obj_name:obj_alias")
    saved_uri = saved_node.from_op.inputs["uri"].val
    assert saved_uri == "local-artifact:///obj_name:obj_alias/obj"
    assert weave.use(saved_node) == data

    merged_node = saved_node

    published_node = weave.ops.publish_artifact(merged_node, "weave_ops", "my_list")
    published_uri = weave.use(published_node)  # published_obj.from_op.inputs["uri"].val
    assert published_uri.startswith("wandb-artifact://")
    assert published_uri.endswith("/obj")
    commit_hash = published_uri.split("my_list/weave_ops:")[1].split("/obj")[0]
    assert weave.use(weave.get(published_uri)) == data
    latest_uri = published_uri.replace(commit_hash, "latest")
    latest_remote_node = weave.ops.get(latest_uri)
    assert weave.use(latest_remote_node) == data

    published_branched_uri = weave.ops.set(
        latest_remote_node[0],
        "test_publish_saved_node_execution_3",
        root_args={"branch": "my-branch"},
    )
    published_branched_data = ["test_publish_saved_node_execution_3"]
    assert published_branched_uri == "local-artifact:///weave_ops:my-branch/obj"
    published_branched_node = weave.ops.get(published_branched_uri)
    assert weave.use(published_branched_node) == published_branched_data

    published_merged_uri = weave.ops.merge(published_branched_node)
    assert published_merged_uri.startswith("wandb-artifact://")
    assert published_merged_uri != published_uri
    published_merged_node = weave.ops.get(published_merged_uri)
    assert weave.use(published_merged_node) == published_branched_data
