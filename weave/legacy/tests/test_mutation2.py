import weave
from weave.legacy.weave import ref_base, uris, weave_internal


def test_mutation_set_direct_call():
    val = weave.legacy.weave.ops.TypedDict.pick({"a": {"b": 5}}, "a")["b"]
    set_result = weave.legacy.weave.ops.set(val, 9)
    assert set_result == {"a": {"b": 9}}


def test_mutation_set_dispatch():
    val = weave.legacy.weave.ops.TypedDict.pick({"a": {"b": 5}}, "a")["b"]
    set_result = val.set(9)
    assert set_result == {"a": {"b": 9}}


def test_mutation_artifact():
    weave.save([1, 2, 3], "art:main")
    art = weave.legacy.weave.ops.get("local-artifact:///art:main/obj")
    art.append(4)
    new_art = weave.storage.get("local-artifact:///art:main/obj")
    assert new_art == [1, 2, 3, 4]


def test_mutation_lazy():
    # This is how weavejs does it.
    weave.save([1, 2, 3], "art:main")
    art = weave.legacy.weave.ops.get("local-artifact:///art:main/obj")

    # Quote lhs expr, so that it is not evaluated.
    quoted_art = weave_internal.const(art)

    expr = weave.legacy.weave.ops.append.lazy_call(quoted_art, 4, {})
    weave.use(expr)

    new_art = weave.storage.get("local-artifact:///art:main/obj")
    assert new_art == [1, 2, 3, 4]


def test_mutation_lazy_works_without_quoting():
    # This relies on "auto quoting behavior". See compile_quote
    weave.save([1, 2, 3], "art:main")
    art = weave.legacy.weave.ops.get("local-artifact:///art:main/obj")

    expr = weave.legacy.weave.ops.append.lazy_call(art, 4, {})
    weave.use(expr)

    new_art = weave.storage.get("local-artifact:///art:main/obj")
    assert new_art == [1, 2, 3, 4]


def test_merge():
    weave.save({"a": 5, "b": 6}, "my-dict:latest")
    dict_obj = weave.legacy.weave.ops.get("local-artifact:///my-dict:latest/obj")
    weave.legacy.weave.ops.set(dict_obj["a"], 17, root_args={"branch": "my-branch"})
    modified_dict_obj = weave.legacy.weave.ops.get("local-artifact:///my-dict:my-branch/obj")
    new_uri = weave.legacy.weave.ops.merge_artifact(modified_dict_obj)
    dict_obj_node = weave.legacy.weave.ops.get(new_uri)
    assert (
        weave.use(dict_obj_node)
        == weave.use(weave.legacy.weave.ops.get("local-artifact:///my-dict:latest/obj"))
        == {"a": 17, "b": 6}
    )


def test_merge_no_version():
    get_node = weave.save({"a": 5, "b": 6}, "my-dict")
    uri = get_node.from_op.inputs["uri"].val  # type: ignore

    # uri now has a direct commit hash for the version
    dict_obj = weave.legacy.weave.ops.get(uri)
    weave.legacy.weave.ops.set(dict_obj["a"], 17, root_args={"branch": "my-branch"})
    modified_dict_obj = weave.legacy.weave.ops.get("local-artifact:///my-dict:my-branch/obj")
    new_uri = weave.legacy.weave.ops.merge_artifact(modified_dict_obj)
    dict_obj_node = weave.legacy.weave.ops.get(new_uri)
    assert weave.use(dict_obj_node) == {"a": 17, "b": 6}


def test_merge_list_type():
    from weave.legacy.weave import object_context

    weave.save([], "my-list:latest")
    obj = weave.legacy.weave.ops.get("local-artifact:///my-list:latest/obj")
    with object_context.object_context():
        obj.append({"a": "x"}, {})
        obj.append([1], {})

    assert weave.use(weave.legacy.weave.ops.get("local-artifact:///my-list:latest/obj")) == [
        {"a": "x"},
        [1],
    ]


def test_artifact_history_local():
    num_versions = 4
    uri = "local-artifact:///art:main/obj"
    weave.save([0], "art:main")
    art = weave.legacy.weave.ops.get(uri)

    for i in range(num_versions):
        art.append(i + 1)

    total_list = list(range(num_versions + 1))
    new_art = weave.storage.get(uri)
    assert new_art == total_list

    for i in range(num_versions):
        new_uri = weave.legacy.weave.ops.undo_artifact(weave.legacy.weave.ops.get(uri))
        # We expect these to be the same since the branch pointer changed
        assert new_uri == uri
        res = weave.storage.get(uri)
        assert res == total_list[: num_versions - i]


def test_artifact_history_local_from_hash():
    num_versions = 4
    uri = "local-artifact:///art:main/obj"
    weave.save([0], "art:main")
    art = weave.legacy.weave.ops.get(uri)

    for i in range(num_versions):
        art.append(i + 1)

    hash_uri = weave.legacy.weave.uris.WeaveURI.parse(uri).to_ref().artifact.uri
    assert "main" not in hash_uri

    total_list = list(range(num_versions + 1))
    new_art = weave.storage.get(hash_uri + "/obj")
    assert new_art == total_list

    new_uri = hash_uri
    for i in range(num_versions):
        new_uri = weave.legacy.weave.ops.undo_artifact(weave.legacy.weave.ops.get(new_uri))
        assert "main" not in new_uri
        res = weave.storage.get(new_uri + "/obj")
        assert res == total_list[: num_versions - i]


def test_artifact_history_remote_with_branch(user_by_api_key_in_env):
    num_versions = 2
    uri = "local-artifact:///art:main/obj"
    weave.save([0], "art:main")
    art = weave.legacy.weave.ops.get(uri)
    published_art_uri = weave.legacy.weave.ops.publish_artifact(art, "art", None, None)

    art = weave.legacy.weave.ops.get(
        f"wandb-artifact:///{user_by_api_key_in_env.username}/weave/art:latest/obj"
    )

    for i in range(num_versions):
        res_uri = art.append(i + 1)
        art = weave.legacy.weave.ops.get(res_uri)

    new_uri = res_uri
    total_list = list(range(num_versions + 1))
    new_art = weave.storage.get(new_uri)
    assert new_art == total_list

    for i in range(num_versions):
        new_uri = weave.legacy.weave.ops.undo_artifact(weave.legacy.weave.ops.get(new_uri))
        res = weave.storage.get(new_uri)
        if i == num_versions - 1:
            assert new_uri.startswith("wandb")
        else:
            assert new_uri.startswith("local")
        assert res == total_list[: num_versions - i]


def test_artifact_history_remote_with_hash(user_by_api_key_in_env):
    num_versions = 2
    uri = "local-artifact:///art:main/obj"
    weave.save([0], "art:main")
    art = weave.legacy.weave.ops.get(uri)
    published_art_uri = weave.legacy.weave.ops.publish_artifact(art, "art", None, None)
    assert "latest" not in published_art_uri
    assert "main" not in published_art_uri

    art = weave.legacy.weave.ops.get(published_art_uri)

    for i in range(num_versions):
        res_uri = art.append(i + 1)
        art = weave.legacy.weave.ops.get(res_uri)

    new_uri = res_uri
    total_list = list(range(num_versions + 1))
    new_art = weave.storage.get(new_uri)
    assert new_art == total_list

    for i in range(num_versions):
        new_uri = weave.legacy.weave.ops.undo_artifact(weave.legacy.weave.ops.get(new_uri))
        res = weave.storage.get(new_uri)
        if i == num_versions - 1:
            assert new_uri.startswith("wandb")
        else:
            assert new_uri.startswith("local")
        assert res == total_list[: num_versions - i]
