import weave
from .. import weave_internal
from .. import uris


def test_mutation_set_direct_call():
    val = weave.ops.TypedDict.pick({"a": {"b": 5}}, "a")["b"]
    set_result = weave.ops.set(val, 9)
    assert set_result == {"a": {"b": 9}}


def test_mutation_set_dispatch():
    val = weave.ops.TypedDict.pick({"a": {"b": 5}}, "a")["b"]
    set_result = val.set(9)
    assert set_result == {"a": {"b": 9}}


def test_mutation_artifact():
    weave.save([1, 2, 3], "art:main")
    art = weave.ops.get("local-artifact:///art:main/obj")
    art.append(4)
    new_art = weave.storage.get("local-artifact:///art:main/obj")
    assert new_art == [1, 2, 3, 4]


def test_mutation_lazy():
    # This is how weavejs does it.
    weave.save([1, 2, 3], "art:main")
    art = weave.ops.get("local-artifact:///art:main/obj")

    # Quote lhs expr, so that it is not evaluated.
    quoted_art = weave_internal.const(art)

    expr = weave.ops.append.lazy_call(quoted_art, 4, {})
    weave.use(expr)

    new_art = weave.storage.get("local-artifact:///art:main/obj")
    assert new_art == [1, 2, 3, 4]


def test_mutation_lazy_works_without_quoting():
    # This relies on "auto quoting behavior". See compile_quote
    weave.save([1, 2, 3], "art:main")
    art = weave.ops.get("local-artifact:///art:main/obj")

    expr = weave.ops.append.lazy_call(art, 4, {})
    weave.use(expr)

    new_art = weave.storage.get("local-artifact:///art:main/obj")
    assert new_art == [1, 2, 3, 4]


def test_merge():
    weave.save({"a": 5, "b": 6}, "my-dict:latest")
    dict_obj = weave.ops.get("local-artifact:///my-dict:latest/obj")
    weave.ops.set(dict_obj["a"], 17, root_args={"branch": "my-branch"})
    modified_dict_obj = weave.ops.get("local-artifact:///my-dict:my-branch/obj")
    new_uri = weave.ops.merge(modified_dict_obj)
    dict_obj_node = weave.ops.get(new_uri)
    assert (
        weave.use(dict_obj_node)
        == weave.use(weave.ops.get("local-artifact:///my-dict:latest/obj"))
        == {"a": 17, "b": 6}
    )


def test_merge_no_version():
    get_node = weave.save({"a": 5, "b": 6}, "my-dict")
    uri = get_node.from_op.inputs["uri"].val  # type: ignore

    # uri now has a direct commit hash for the version
    dict_obj = weave.ops.get(uri)
    weave.ops.set(dict_obj["a"], 17, root_args={"branch": "my-branch"})
    modified_dict_obj = weave.ops.get("local-artifact:///my-dict:my-branch/obj")
    new_uri = weave.ops.merge(modified_dict_obj)
    dict_obj_node = weave.ops.get(new_uri)
    assert weave.use(dict_obj_node) == {"a": 17, "b": 6}
